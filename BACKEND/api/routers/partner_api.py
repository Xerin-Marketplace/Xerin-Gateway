from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from api.deps import get_current_user, get_db
from api.enums import LogisticsCompanyPermission, LogisticsMemberRole, ShipmentStatus
from api.models import LogisticsCompanyUser, PartnerCredential, PartnerRequestLog, Shipment, ShipmentTrackingEvent, User
from api.schemas import PartnerCredentialCreate, PartnerCredentialIssuedResponse, PartnerCredentialResponse, PartnerRequestLogResponse, ShipmentTrackingEventCreate
from api.services.partner_security_service import begin_idempotency, complete_idempotency, create_credential, require_partner_scope

management_router=APIRouter(prefix="/partner-security",tags=["Partner Security"])
partner_router=APIRouter(prefix="/partner",tags=["Partner API"])
ROLE_PERMISSIONS={
    LogisticsMemberRole.company_admin:set(LogisticsCompanyPermission),
    LogisticsMemberRole.operations_manager:{LogisticsCompanyPermission.integrations_manage},
}


def member(db,user):
    row=db.query(LogisticsCompanyUser).filter(LogisticsCompanyUser.user_id==user.id,LogisticsCompanyUser.is_active.is_(True)).first()
    if row is None:raise HTTPException(403,"Active logistics company membership required")
    permissions=set(LogisticsCompanyPermission) if row.is_primary_contact else set(ROLE_PERMISSIONS.get(row.member_role,set()))
    for value in row.permissions_json or []:
        try:permissions.add(LogisticsCompanyPermission(value))
        except ValueError:pass
    if LogisticsCompanyPermission.integrations_manage not in permissions:raise HTTPException(403,"Company integration permission required")
    return row


def commit(db):
    try:db.commit()
    except IntegrityError as exc:db.rollback();raise HTTPException(409,"Conflicting partner security operation") from exc


@management_router.get("/credentials",response_model=list[PartnerCredentialResponse])
def credentials(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    membership=member(db,user);return db.query(PartnerCredential).filter(PartnerCredential.logistics_company_id==membership.logistics_company_id).order_by(PartnerCredential.created_at.desc()).all()


@management_router.post("/credentials",response_model=PartnerCredentialIssuedResponse,status_code=201)
def issue(data:PartnerCredentialCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    membership=member(db,user)
    try:row,secret=create_credential(db,company_id=membership.logistics_company_id,name=data.name,scopes=data.scopes,allowed_cidrs=data.allowed_cidrs,rate_limit=data.rate_limit_per_minute,expires_at=data.expires_at,actor_id=user.id);commit(db);db.refresh(row);return {"credential":row,"secret":secret}
    except ValueError as exc:db.rollback();raise HTTPException(422,str(exc)) from exc


@management_router.post("/credentials/{credential_id}/rotate",response_model=PartnerCredentialIssuedResponse,status_code=201)
def rotate(credential_id:UUID,data:PartnerCredentialCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    membership=member(db,user);old=db.query(PartnerCredential).filter(PartnerCredential.id==credential_id,PartnerCredential.logistics_company_id==membership.logistics_company_id).with_for_update().first()
    if old is None:raise HTTPException(404,"Partner credential not found")
    if old.status!="active":raise HTTPException(409,"Only active credentials can be rotated")
    try:
        row,secret=create_credential(db,company_id=membership.logistics_company_id,name=data.name,scopes=data.scopes,allowed_cidrs=data.allowed_cidrs,rate_limit=data.rate_limit_per_minute,expires_at=data.expires_at,actor_id=user.id,rotated_from_id=old.id)
        old.status="rotated";old.revoked_at=datetime.now(timezone.utc);old.revoked_by_id=user.id;commit(db);db.refresh(row);return {"credential":row,"secret":secret}
    except ValueError as exc:db.rollback();raise HTTPException(422,str(exc)) from exc


@management_router.post("/credentials/{credential_id}/revoke",response_model=PartnerCredentialResponse)
def revoke(credential_id:UUID,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    membership=member(db,user);row=db.query(PartnerCredential).filter(PartnerCredential.id==credential_id,PartnerCredential.logistics_company_id==membership.logistics_company_id).with_for_update().first()
    if row is None:raise HTTPException(404,"Partner credential not found")
    if row.status=="active":row.status="revoked";row.revoked_at=datetime.now(timezone.utc);row.revoked_by_id=user.id
    commit(db);db.refresh(row);return row


@management_router.get("/request-logs",response_model=list[PartnerRequestLogResponse])
def logs(page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=100),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    membership=member(db,user);return db.query(PartnerRequestLog).filter(PartnerRequestLog.logistics_company_id==membership.logistics_company_id).order_by(PartnerRequestLog.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()


@partner_router.get("/shipments/{tracking_number}")
def partner_shipment(tracking_number:str,db:Session=Depends(get_db),credential:PartnerCredential=Depends(require_partner_scope("shipments:read"))):
    shipment=db.query(Shipment).options(selectinload(Shipment.tracking_events)).filter(Shipment.logistics_company_id==credential.logistics_company_id,Shipment.tracking_number==tracking_number).first()
    if shipment is None:raise HTTPException(404,"Shipment not found")
    return {"id":str(shipment.id),"order_id":str(shipment.order_id),"tracking_number":shipment.tracking_number,"status":shipment.status.value,"dispatched_at":shipment.dispatched_at,"delivered_at":shipment.delivered_at,"events":[{"status":row.status.value,"location":row.location,"notes":row.notes,"created_at":row.created_at} for row in shipment.tracking_events]}


PARTNER_TRANSITIONS={
    ShipmentStatus.ready_for_dispatch:{ShipmentStatus.dispatched},
    ShipmentStatus.dispatched:{ShipmentStatus.in_transit,ShipmentStatus.delivery_failed},
    ShipmentStatus.in_transit:{ShipmentStatus.out_for_delivery,ShipmentStatus.delivery_failed,ShipmentStatus.returned_to_sender},
    ShipmentStatus.out_for_delivery:{ShipmentStatus.delivery_failed,ShipmentStatus.returned_to_sender},
    ShipmentStatus.delivery_failed:{ShipmentStatus.out_for_delivery,ShipmentStatus.returned_to_sender},
}


@partner_router.post("/shipments/{shipment_id}/events")
async def partner_tracking_event(shipment_id:UUID,data:ShipmentTrackingEventCreate,request:Request,idempotency_key:str|None=Header(None,alias="Idempotency-Key"),db:Session=Depends(get_db),credential:PartnerCredential=Depends(require_partner_scope("tracking:write"))):
    record,replayed=begin_idempotency(db,credential=credential,request=request,key=idempotency_key)
    if replayed:return JSONResponse(status_code=record.response_status,content=record.response_body)
    shipment=db.query(Shipment).filter(Shipment.id==shipment_id,Shipment.logistics_company_id==credential.logistics_company_id).with_for_update().first()
    if shipment is None:raise HTTPException(404,"Shipment not found")
    if data.status==ShipmentStatus.delivered:raise HTTPException(409,"Delivered status requires XERIN recipient OTP proof")
    if data.status not in PARTNER_TRANSITIONS.get(shipment.status,set()):raise HTTPException(409,f"Invalid shipment transition: {shipment.status.value} -> {data.status.value}")
    shipment.status=data.status;now=datetime.now(timezone.utc)
    if data.status==ShipmentStatus.dispatched and shipment.dispatched_at is None:shipment.dispatched_at=now
    if data.tracking_number:shipment.tracking_number=data.tracking_number.strip()
    if data.carrier_name:shipment.carrier_name=data.carrier_name.strip()
    db.add(ShipmentTrackingEvent(shipment_id=shipment.id,status=data.status,location=data.location,notes=data.notes or "Signed partner tracking update"))
    body={"shipment_id":str(shipment.id),"status":data.status.value,"accepted":True}
    complete_idempotency(record,200,body)
    if hasattr(request.state,"partner_request_log_id"):db.query(PartnerRequestLog).filter(PartnerRequestLog.id==request.state.partner_request_log_id).update({PartnerRequestLog.response_status:200})
    commit(db);return body
