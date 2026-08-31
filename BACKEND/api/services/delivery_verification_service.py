import io
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from api.config import settings
from api.enums import SellerOrderStatus, ShipmentStatus
from api.models import (
    OrderStatus, OrderStatusHistory, PaymentDispute, SellerOrder, Shipment, ShipmentDeliveryProof,
    ShipmentDeliveryProofEvent, ShipmentTrackingEvent,
)
from api.security import generate_otp, hash_otp, verify_otp_hash
from api.services.logistics_wallet_service import release_verified_delivery_entitlement
from api.services.escrow_service import arm_shipment_seller_escrow_after_delivery


class DeliveryVerificationError(ValueError):
    def __init__(self, message, status_code=409):
        super().__init__(message); self.status_code = status_code


@dataclass
class StoredImage:
    url: str
    original_filename: str
    mime_type: str
    file_size: int


def distance_meters(lat1, lon1, lat2, lon2):
    values = [math.radians(float(v)) for v in (lat1, lon1, lat2, lon2)]
    a1, o1, a2, o2 = values
    delta_a, delta_o = a2-a1, o2-o1
    h = math.sin(delta_a/2)**2 + math.cos(a1)*math.cos(a2)*math.sin(delta_o/2)**2
    return Decimal(str(round(6371000 * 2 * math.atan2(math.sqrt(h), math.sqrt(1-h)), 2)))


async def store_delivery_image(file: UploadFile, shipment_id) -> StoredImage:
    raw = await file.read()
    if not raw: raise DeliveryVerificationError("Delivery proof image is empty", 400)
    if len(raw) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise DeliveryVerificationError(f"Delivery proof image must not exceed {settings.MAX_UPLOAD_SIZE_MB} MB", 413)
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            detected=(probe.format or "").upper(); probe.verify()
        if detected not in {"JPEG","PNG","WEBP"}: raise DeliveryVerificationError("Only JPEG, PNG and WEBP images are allowed", 400)
        image=Image.open(io.BytesIO(raw)); image.load()
    except DeliveryVerificationError: raise
    except (UnidentifiedImageError,OSError,ValueError) as exc: raise DeliveryVerificationError("Invalid delivery proof image",400) from exc
    image=ImageOps.exif_transpose(image)
    if image.width>2400 or image.height>2400: image.thumbnail((2400,2400),Image.Resampling.LANCZOS)
    relative=Path("delivery-proofs")/str(shipment_id); absolute=settings.upload_path/relative; absolute.mkdir(parents=True,exist_ok=True)
    filename=f"{uuid.uuid4()}.webp"; path=absolute/filename
    image.convert("RGB").save(path,format="WEBP",quality=88,method=6)
    public=f"{settings.PUBLIC_BASE_URL.rstrip('/')}/uploads/{relative.as_posix()}/{filename}" if settings.PUBLIC_BASE_URL else f"/uploads/{relative.as_posix()}/{filename}"
    return StoredImage(public,Path(file.filename or "delivery-proof").name[:255],"image/webp",path.stat().st_size)


def initiate_delivery_proof(db: Session, *, shipment: Shipment, actor_id, recipient_name, latitude, longitude, notes, image):
    if shipment.status != ShipmentStatus.out_for_delivery:
        raise DeliveryVerificationError("Shipment must be out for delivery before POD can start")
    if not shipment.logistics_company_id:
        raise DeliveryVerificationError("Shipment has no assigned logistics company")
    address=shipment.order.shipping_address
    if not address or address.latitude is None or address.longitude is None:
        raise DeliveryVerificationError("Order delivery destination has no confirmed GPS pin",422)
    distance=distance_meters(latitude,longitude,address.latitude,address.longitude)
    if distance > settings.DELIVERY_PROOF_MAX_DISTANCE_METERS:
        raise DeliveryVerificationError(f"Delivery evidence is {distance} meters from the confirmed destination",422)
    otp=generate_otp(); now=datetime.now(timezone.utc)
    proof=db.query(ShipmentDeliveryProof).filter(ShipmentDeliveryProof.shipment_id==shipment.id).with_for_update().first()
    if proof and proof.status=="verified": raise DeliveryVerificationError("Delivery is already verified")
    if proof and proof.status=="disputed": raise DeliveryVerificationError("Delivery proof is disputed")
    values=dict(order_id=shipment.order_id,customer_id=shipment.order.user_id,logistics_company_id=shipment.logistics_company_id,status="pending_otp",
        recipient_name=recipient_name,recipient_phone_last4=(address.recipient_phone or shipment.order.user.phone or "")[-4:] or None,
        photo_url=image.url,original_filename=image.original_filename,mime_type=image.mime_type,file_size=image.file_size,
        delivery_latitude=latitude,delivery_longitude=longitude,destination_latitude=address.latitude,destination_longitude=address.longitude,
        distance_from_destination_meters=distance,otp_hash=hash_otp(otp),otp_expires_at=now+timedelta(minutes=settings.DELIVERY_OTP_EXPIRE_MINUTES),
        otp_attempts=0,notes=notes,initiated_by_id=actor_id,verified_by_id=None,verified_at=None,settlement_status="held")
    if proof is None: proof=ShipmentDeliveryProof(shipment_id=shipment.id,**values);db.add(proof);db.flush()
    else:
        for key,value in values.items(): setattr(proof,key,value)
    db.add(ShipmentDeliveryProofEvent(proof=proof,action="otp_issued",note="POD evidence captured and recipient OTP issued",created_by_id=actor_id))
    db.flush(); return proof,otp


def verify_delivery_proof(db: Session, *, proof: ShipmentDeliveryProof, otp_code: str, actor_id):
    if proof.status != "pending_otp": raise DeliveryVerificationError(f"Delivery proof cannot be verified from status {proof.status}")
    now=datetime.now(timezone.utc)
    if proof.otp_expires_at < now:
        proof.status="expired";db.add(ShipmentDeliveryProofEvent(proof=proof,action="otp_expired",created_by_id=actor_id));raise DeliveryVerificationError("Delivery OTP expired",400)
    if proof.otp_attempts >= settings.DELIVERY_OTP_MAX_ATTEMPTS: raise DeliveryVerificationError("Maximum delivery OTP attempts exceeded",429)
    proof.otp_attempts += 1
    if not verify_otp_hash(otp_code,proof.otp_hash):
        db.add(ShipmentDeliveryProofEvent(proof=proof,action="otp_failed",note=f"Failed attempt {proof.otp_attempts}",created_by_id=actor_id));raise DeliveryVerificationError("Invalid delivery OTP",400)
    unresolved=db.query(PaymentDispute).filter(PaymentDispute.order_id==proof.order_id,PaymentDispute.status.in_(["open","pending","under_review","action_required"])).first()
    if unresolved:
        proof.settlement_status="blocked";raise DeliveryVerificationError("Order has an unresolved payment dispute")
    shipment=proof.shipment
    if shipment.status != ShipmentStatus.out_for_delivery: raise DeliveryVerificationError("Shipment is no longer out for delivery")
    proof.status="verified";proof.verified_at=now;proof.verified_by_id=actor_id
    shipment.status=ShipmentStatus.delivered;shipment.delivered_at=now
    # F6: verified recipient delivery starts the seller protection clock for
    # this shipment. It does not release seller funds yet.
    arm_shipment_seller_escrow_after_delivery(
        db,
        shipment_id=shipment.id,
        order_id=shipment.order_id,
        verified_at=now,
        actor_id=actor_id,
    )
    seller_order=db.query(SellerOrder).filter(SellerOrder.order_id==shipment.order_id,SellerOrder.seller_id==shipment.seller_id,SellerOrder.store_id==shipment.store_id).first()
    if seller_order: seller_order.status=SellerOrderStatus.delivered;seller_order.delivered_at=now
    db.add(ShipmentTrackingEvent(shipment_id=shipment.id,status=ShipmentStatus.delivered,location=f"{proof.delivery_latitude},{proof.delivery_longitude}",notes="Delivered after recipient OTP and GPS verification",created_by_id=actor_id))
    db.add(ShipmentDeliveryProofEvent(proof=proof,action="verified",note="Recipient OTP verified",created_by_id=actor_id))
    all_shipments=db.query(Shipment).filter(Shipment.order_id==shipment.order_id).with_for_update().all()
    all_verified = all(
        row.status == ShipmentStatus.delivered
        and row.delivery_proof is not None
        and row.delivery_proof.status == "verified"
        for row in all_shipments
    )
    if all_verified:
        shipment.order.status=OrderStatus.delivered
        db.add(OrderStatusHistory(order_id=shipment.order_id,status=OrderStatus.delivered.value,notes="All shipments completed with recipient OTP proof of delivery",created_by_id=actor_id))
        transaction=release_verified_delivery_entitlement(db,order=shipment.order,proof_id=proof.id)
        for row in all_shipments:
            if transaction:
                row.delivery_proof.logistics_release_transaction_id=transaction.id
                row.delivery_proof.settlement_status="released"
            else:
                row.delivery_proof.settlement_status="awaiting_cod_remittance"
    db.flush();return proof


def dispute_delivery_proof(db: Session, *, proof, customer_id, reason, notes):
    if proof.customer_id != customer_id: raise DeliveryVerificationError("Not authorized",403)
    if proof.status != "pending_otp": raise DeliveryVerificationError("Only pending delivery proof can be disputed")
    proof.status="disputed";proof.disputed_at=datetime.now(timezone.utc);proof.dispute_reason=reason;proof.dispute_notes=notes;proof.settlement_status="blocked"
    db.add(ShipmentDeliveryProofEvent(proof=proof,action="disputed",note=notes or reason,created_by_id=customer_id));db.flush();return proof
