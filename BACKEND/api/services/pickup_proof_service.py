from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from api.config import settings
from api.enums import NotificationEvent, ShipmentStatus
from api.models import (
    LogisticsCompany,
    Order,
    Shipment,
    ShipmentHandover,
    ShipmentPickupProof,
    ShipmentTrackingEvent,
)
from api.services.notification_service import notification_service
from api.services.escrow_service import (
    dispute_shipment_seller_entitlement,
    release_shipment_seller_entitlement,
)


ALLOWED_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
MAX_IMAGE_DIMENSION = 3200


class PickupProofError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


def _release_verified_seller_funds(db: Session, *, proof: ShipmentPickupProof, actor_id, trigger: str) -> None:
    try:
        release_shipment_seller_entitlement(
            db,
            proof=proof,
            actor_id=actor_id,
            trigger=trigger,
        )
    except ValueError as exc:
        raise PickupProofError(
            str(exc),
            code="seller_settlement_conflict",
            status_code=409,
        ) from exc


def _block_disputed_seller_funds(db: Session, *, proof: ShipmentPickupProof, actor_id) -> None:
    try:
        dispute_shipment_seller_entitlement(db, proof=proof, actor_id=actor_id)
    except ValueError as exc:
        raise PickupProofError(
            str(exc),
            code="seller_settlement_already_released",
            status_code=409,
        ) from exc


@dataclass(frozen=True)
class StoredPickupProofImage:
    image_url: str
    original_filename: str
    mime_type: str
    file_size: int


def _public_url(relative_path: Path) -> str:
    clean = relative_path.as_posix().lstrip("/")
    if settings.PUBLIC_BASE_URL:
        return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/uploads/{clean}"
    return f"/uploads/{clean}"


async def store_pickup_proof_image(
    file: UploadFile,
    *,
    shipment_id: UUID,
) -> StoredPickupProofImage:
    raw = await file.read()
    if not raw:
        raise PickupProofError(
            "Pickup proof image is empty.",
            code="pickup_proof_image_empty",
            status_code=400,
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(raw) > max_bytes:
        raise PickupProofError(
            f"Pickup proof image must not exceed {settings.MAX_UPLOAD_SIZE_MB} MB.",
            code="pickup_proof_image_too_large",
            status_code=413,
        )

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            detected = (probe.format or "").upper()
            probe.verify()
        if detected not in ALLOWED_FORMATS:
            raise PickupProofError(
                "Only JPEG, PNG and WEBP pickup proof images are allowed.",
                code="pickup_proof_invalid_format",
                status_code=400,
            )
        image = Image.open(io.BytesIO(raw))
        image.load()
    except PickupProofError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise PickupProofError(
            "Uploaded pickup proof is not a valid image.",
            code="pickup_proof_invalid_image",
            status_code=400,
        ) from exc

    image = ImageOps.exif_transpose(image)
    if image.width > MAX_IMAGE_DIMENSION or image.height > MAX_IMAGE_DIMENSION:
        image.thumbnail(
            (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION),
            Image.Resampling.LANCZOS,
        )

    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGB")

    relative_dir = Path("pickup-proofs") / str(shipment_id)
    absolute_dir = settings.upload_path / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    image_name = f"{uuid.uuid4()}.webp"
    image_path = absolute_dir / image_name

    if image.mode == "RGBA":
        image.save(image_path, format="WEBP", quality=88, method=6)
    else:
        image.convert("RGB").save(image_path, format="WEBP", quality=88, method=6)

    return StoredPickupProofImage(
        image_url=_public_url(relative_dir / image_name),
        original_filename=Path(file.filename or "pickup-proof").name[:255],
        mime_type="image/webp",
        file_size=image_path.stat().st_size,
    )


def auto_approve_if_expired(
    db: Session,
    proof: ShipmentPickupProof,
    *,
    commit: bool = True,
) -> ShipmentPickupProof:
    if proof.status in {"approved", "auto_approved"}:
        _release_verified_seller_funds(db, proof=proof, actor_id=proof.customer_reviewed_by_id, trigger="pickup_auto_approved" if proof.status == "auto_approved" else "pickup_customer_approved")
        if commit:
            db.commit()
            db.refresh(proof)
        return proof
    if proof.status != "pending":
        return proof

    now = datetime.now(timezone.utc)
    if proof.review_deadline > now:
        return proof

    proof.status = "auto_approved"
    proof.customer_reviewed_at = now
    proof.problem_reason = None
    proof.problem_notes = None

    db.add(
        ShipmentTrackingEvent(
            shipment_id=proof.shipment_id,
            status=proof.shipment.status,
            notes="Pickup proof auto-approved after customer review window expired.",
            created_by_id=None,
        )
    )
    _release_verified_seller_funds(db, proof=proof, actor_id=None, trigger="pickup_auto_approved")

    if commit:
        db.commit()
        db.refresh(proof)
    return proof


def create_pickup_proof(
    db: Session,
    *,
    shipment: Shipment,
    handover: ShipmentHandover,
    customer_id: UUID,
    logistics_company_id: UUID,
    uploaded_by_id: UUID,
    image: StoredPickupProofImage,
    latitude,
    longitude,
    courier_reference: str | None,
    notes: str | None,
) -> ShipmentPickupProof:
    existing = (
        db.query(ShipmentPickupProof)
        .filter(ShipmentPickupProof.shipment_id == shipment.id)
        .first()
    )
    if existing:
        return existing

    if handover.status != "seller_confirmed" or handover.seller_confirmed_at is None:
        raise PickupProofError(
            "Seller must confirm physical handover before pickup proof can be recorded.",
            code="seller_handover_required",
            status_code=409,
        )

    if shipment.status != ShipmentStatus.ready_for_dispatch:
        raise PickupProofError(
            "Pickup proof can only be recorded for a shipment ready for dispatch.",
            code="shipment_not_ready_for_pickup_proof",
            status_code=409,
        )

    now = datetime.now(timezone.utc)
    proof = ShipmentPickupProof(
        shipment_id=shipment.id,
        handover_id=handover.id,
        order_id=shipment.order_id,
        customer_id=customer_id,
        seller_id=shipment.seller_id,
        logistics_company_id=logistics_company_id,
        photo_url=image.image_url,
        original_filename=image.original_filename,
        mime_type=image.mime_type,
        file_size=image.file_size,
        pickup_latitude=latitude,
        pickup_longitude=longitude,
        courier_reference=(courier_reference or "").strip() or None,
        notes=(notes or "").strip() or None,
        status="pending",
        review_deadline=now + timedelta(
            minutes=max(1, settings.PICKUP_PROOF_REVIEW_MINUTES)
        ),
        uploaded_by_id=uploaded_by_id,
    )
    db.add(proof)

    shipment.status = ShipmentStatus.dispatched
    if shipment.dispatched_at is None:
        shipment.dispatched_at = now

    db.add(
        ShipmentTrackingEvent(
            shipment_id=shipment.id,
            status=ShipmentStatus.dispatched,
            location=f"{latitude},{longitude}",
            notes="Courier collected seller package and uploaded pickup proof.",
            created_by_id=uploaded_by_id,
        )
    )

    notification_service.create_notification(
        db,
        user_id=customer_id,
        event=NotificationEvent.delivery_updated,
        title="Review pickup evidence",
        message="Your seller package has been collected. Review the pickup photo and confirm whether it appears to match your order.",
        data={
            "pickup_proof_id": str(proof.id),
            "shipment_id": str(shipment.id),
            "order_id": str(shipment.order_id),
        },
        action_url=f"/account/orders/{shipment.order_id}",
        commit=False,
    )

    db.commit()
    db.refresh(proof)
    return proof


def approve_pickup_proof(
    db: Session,
    *,
    proof: ShipmentPickupProof,
    customer_id: UUID,
) -> ShipmentPickupProof:
    proof = auto_approve_if_expired(db, proof, commit=False)
    if proof.customer_id != customer_id:
        raise PickupProofError(
            "Pickup proof not found.",
            code="pickup_proof_not_found",
            status_code=404,
        )
    if proof.status in {"approved", "auto_approved"}:
        _release_verified_seller_funds(db, proof=proof, actor_id=customer_id, trigger="pickup_auto_approved" if proof.status == "auto_approved" else "pickup_customer_approved")
        db.commit()
        db.refresh(proof)
        return proof
    if proof.status == "disputed":
        raise PickupProofError(
            "A disputed pickup proof cannot be approved without dispute resolution.",
            code="pickup_proof_already_disputed",
            status_code=409,
        )

    proof.status = "approved"
    proof.customer_reviewed_at = datetime.now(timezone.utc)
    proof.customer_reviewed_by_id = customer_id
    proof.problem_reason = None
    proof.problem_notes = None

    db.add(
        ShipmentTrackingEvent(
            shipment_id=proof.shipment_id,
            status=proof.shipment.status,
            notes="Customer approved pickup evidence.",
            created_by_id=customer_id,
        )
    )
    _release_verified_seller_funds(db, proof=proof, actor_id=customer_id, trigger="pickup_customer_approved")
    db.commit()
    db.refresh(proof)
    return proof


def dispute_pickup_proof(
    db: Session,
    *,
    proof: ShipmentPickupProof,
    customer_id: UUID,
    reason: str,
    notes: str | None,
) -> ShipmentPickupProof:
    proof = auto_approve_if_expired(db, proof, commit=False)
    if proof.customer_id != customer_id:
        raise PickupProofError(
            "Pickup proof not found.",
            code="pickup_proof_not_found",
            status_code=404,
        )
    if proof.status in {"approved", "auto_approved"}:
        raise PickupProofError(
            "Pickup proof has already been approved.",
            code="pickup_proof_already_approved",
            status_code=409,
        )
    if proof.status == "disputed":
        db.commit()
        db.refresh(proof)
        return proof

    proof.status = "disputed"
    proof.customer_reviewed_at = datetime.now(timezone.utc)
    proof.customer_reviewed_by_id = customer_id
    proof.problem_reason = reason
    proof.problem_notes = (notes or "").strip() or None

    db.add(
        ShipmentTrackingEvent(
            shipment_id=proof.shipment_id,
            status=proof.shipment.status,
            notes=f"Customer reported a pickup proof problem: {reason}.",
            created_by_id=customer_id,
        )
    )
    _block_disputed_seller_funds(db, proof=proof, actor_id=customer_id)

    # Notify the seller that settlement must remain held pending later review.
    seller_user_id = proof.seller.user_id if proof.seller else None
    if seller_user_id:
        notification_service.create_notification(
            db,
            user_id=seller_user_id,
            event=NotificationEvent.system_alert,
            title="Pickup evidence disputed",
            message="The customer reported a problem with pickup evidence. Seller settlement will remain held pending review.",
            data={
                "pickup_proof_id": str(proof.id),
                "shipment_id": str(proof.shipment_id),
                "order_id": str(proof.order_id),
            },
            action_url="/seller/orders",
            commit=False,
        )

    db.commit()
    db.refresh(proof)
    return proof
