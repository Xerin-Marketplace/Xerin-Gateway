from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from api.config import settings
from api.deps import get_current_user, get_db
from api.enums import LogisticsCompanyPermission, LogisticsMemberRole
from api.models import LogisticsCompanyUser, Order, Shipment, ShipmentDeliveryProof, User
from api.routers.email import send_otp_email
from api.routers.sms import send_sms
from api.schemas import DeliveryProofDisputeRequest, DeliveryProofResponse, DeliveryProofStartResponse, DeliveryProofVerifyRequest
from api.services.delivery_verification_service import DeliveryVerificationError, dispute_delivery_proof, initiate_delivery_proof, resend_delivery_otp, store_delivery_image, verify_delivery_proof

router=APIRouter(prefix="/delivery-verification",tags=["Delivery Verification"])
ROLE_PERMISSIONS={
    LogisticsMemberRole.company_admin:set(LogisticsCompanyPermission),
    LogisticsMemberRole.operations_manager:{LogisticsCompanyPermission.shipments_manage},
    LogisticsMemberRole.dispatcher:{LogisticsCompanyPermission.shipments_manage},
    LogisticsMemberRole.driver:{LogisticsCompanyPermission.shipments_manage},
}


def member(db,user):
    row=db.query(LogisticsCompanyUser).filter(LogisticsCompanyUser.user_id==user.id,LogisticsCompanyUser.is_active.is_(True)).first()
    if row is None: raise HTTPException(403,"Active logistics company membership required")
    permissions=set(LogisticsCompanyPermission) if row.is_primary_contact else set(ROLE_PERMISSIONS.get(row.member_role,set()))
    for value in row.permissions_json or []:
        try: permissions.add(LogisticsCompanyPermission(value))
        except ValueError: pass
    if LogisticsCompanyPermission.shipments_manage not in permissions: raise HTTPException(403,"Company shipment permission required")
    return row


def _send_recipient_otp(*, shipment: Shipment, otp: str):
    address = shipment.order.shipping_address
    customer = shipment.order.user
    phone = (address.recipient_phone if address else None) or customer.phone
    channels = []

    if phone:
        try:
            send_sms(
                to=phone,
                message=(
                    f"Your Xerin delivery verification code is {otp}. "
                    f"It expires in {settings.DELIVERY_OTP_EXPIRE_MINUTES} minutes."
                ),
            )
            channels.append("sms")
        except Exception:
            pass

    if customer.email:
        try:
            send_otp_email(
                to=customer.email,
                otp=otp,
                recipient_name=address.recipient_name if address else None,
                purpose="delivery_verification",
                expires_minutes=settings.DELIVERY_OTP_EXPIRE_MINUTES,
            )
            channels.append("email")
        except Exception:
            pass

    if not channels:
        raise DeliveryVerificationError("Could not deliver recipient OTP", 503)

    return channels



def commit(db):
    try: db.commit()
    except IntegrityError as exc: db.rollback();raise HTTPException(409,"Conflicting delivery verification operation") from exc


@router.post("/logistics/shipments/{shipment_id}/start",response_model=DeliveryProofStartResponse,status_code=201)
async def start(shipment_id:UUID,recipient_name:str=Form(...,min_length=2,max_length=150),latitude:Decimal=Form(...,ge=-90,le=90),longitude:Decimal=Form(...,ge=-180,le=180),notes:str|None=Form(None,max_length=2000),photo:UploadFile=File(...),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    membership=member(db,user)
    shipment=db.query(Shipment).options(joinedload(Shipment.order).joinedload(Order.shipping_address),joinedload(Shipment.order).joinedload(Order.user)).filter(Shipment.id==shipment_id,Shipment.logistics_company_id==membership.logistics_company_id).with_for_update(of=Shipment).first()
    if shipment is None: raise HTTPException(404,"Shipment not found for this logistics company")
    try:
        image=await store_delivery_image(photo,shipment.id)
        proof,otp=initiate_delivery_proof(db,shipment=shipment,actor_id=user.id,recipient_name=recipient_name,latitude=latitude,longitude=longitude,notes=notes,image=image)
        channels=_send_recipient_otp(shipment=shipment,otp=otp)
        commit(db);db.refresh(proof)
        return {"proof":proof,"otp_delivery_channels":channels,"dev_otp":otp if settings.DEBUG else None}
    except DeliveryVerificationError as exc:
        db.rollback();raise HTTPException(exc.status_code,str(exc)) from exc


@router.post(
    "/logistics/proofs/{proof_id}/resend-otp",
    response_model=DeliveryProofStartResponse,
)
def resend_otp(
    proof_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = member(db, user)
    proof = (
        db.query(ShipmentDeliveryProof)
        .options(
            joinedload(ShipmentDeliveryProof.shipment)
            .joinedload(Shipment.order)
            .joinedload(Order.shipping_address),
            joinedload(ShipmentDeliveryProof.shipment)
            .joinedload(Shipment.order)
            .joinedload(Order.user),
            selectinload(ShipmentDeliveryProof.events),
        )
        .filter(
            ShipmentDeliveryProof.id == proof_id,
            ShipmentDeliveryProof.logistics_company_id
            == membership.logistics_company_id,
        )
        .with_for_update(of=ShipmentDeliveryProof)
        .first()
    )
    if proof is None:
        raise HTTPException(404, "Delivery proof not found")

    try:
        proof, otp = resend_delivery_otp(db, proof=proof, actor_id=user.id)
        channels = _send_recipient_otp(shipment=proof.shipment, otp=otp)
        commit(db)
        db.refresh(proof)
        return {
            "proof": proof,
            "otp_delivery_channels": channels,
            "dev_otp": otp if settings.DEBUG else None,
        }
    except DeliveryVerificationError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.post("/logistics/proofs/{proof_id}/verify",response_model=DeliveryProofResponse)
def verify(proof_id:UUID,data:DeliveryProofVerifyRequest,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    membership=member(db,user)
    proof=db.query(ShipmentDeliveryProof).options(joinedload(ShipmentDeliveryProof.shipment).joinedload(Shipment.order),selectinload(ShipmentDeliveryProof.events)).filter(ShipmentDeliveryProof.id==proof_id,ShipmentDeliveryProof.logistics_company_id==membership.logistics_company_id).with_for_update(of=ShipmentDeliveryProof).first()
    if proof is None: raise HTTPException(404,"Delivery proof not found")
    try: verify_delivery_proof(db,proof=proof,otp_code=data.otp_code,actor_id=user.id);commit(db);db.refresh(proof);return proof
    except DeliveryVerificationError as exc:
        # Persist attempt counters, expiry and blocked-state audit evidence.
        commit(db);raise HTTPException(exc.status_code,str(exc)) from exc


@router.get("/customer/my",response_model=list[DeliveryProofResponse])
def mine(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return db.query(ShipmentDeliveryProof).options(selectinload(ShipmentDeliveryProof.events)).filter(ShipmentDeliveryProof.customer_id==user.id).order_by(ShipmentDeliveryProof.created_at.desc()).all()


@router.post("/customer/proofs/{proof_id}/dispute",response_model=DeliveryProofResponse)
def dispute(proof_id:UUID,data:DeliveryProofDisputeRequest,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    proof=db.query(ShipmentDeliveryProof).options(selectinload(ShipmentDeliveryProof.events)).filter(ShipmentDeliveryProof.id==proof_id).with_for_update(of=ShipmentDeliveryProof).first()
    if proof is None: raise HTTPException(404,"Delivery proof not found")
    try: dispute_delivery_proof(db,proof=proof,customer_id=user.id,reason=data.reason,notes=data.notes);commit(db);db.refresh(proof);return proof
    except DeliveryVerificationError as exc: db.rollback();raise HTTPException(exc.status_code,str(exc)) from exc
