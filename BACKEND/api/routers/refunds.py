from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from api.deps import get_db,get_current_user
from api.enums import PermissionCode,RefundStatus
from api.models import Refund,Order,OrderStatus,User
from api.permissions import require_permission
from api.schemas import RefundCreate,RefundResponse,RefundReview,RefundProcess
from api.services.refund_service import create_refund_request,transition_refund
router=APIRouter(prefix="/refunds",tags=["Refunds"])
def commit(db):
    try:db.commit()
    except IntegrityError as exc:db.rollback();raise HTTPException(409,"Conflicting or duplicate refund operation") from exc

def get_locked(db,refund_id):
    r=db.query(Refund).filter(Refund.id==refund_id).with_for_update().first()
    if not r:raise HTTPException(404,"Refund not found")
    return r

@router.post("",response_model=RefundResponse,status_code=status.HTTP_201_CREATED)
def request_refund(data:RefundCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    order=db.query(Order).filter(Order.id==data.order_id,Order.user_id==user.id).with_for_update().first()
    if not order:raise HTTPException(404,"Order not found")
    if order.status not in {OrderStatus.paid,OrderStatus.processing,OrderStatus.shipped,OrderStatus.delivered}:raise HTTPException(409,"Order is not eligible for refund")
    try:r=create_refund_request(db,order=order,user_id=user.id,data=data);commit(db);db.refresh(r);return r
    except ValueError as exc:db.rollback();raise HTTPException(422,str(exc)) from exc

@router.get("",response_model=list[RefundResponse])
def my_refunds(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return db.query(Refund).filter(Refund.requested_by_id==user.id).order_by(Refund.requested_at.desc()).all()

@router.get("/admin",response_model=list[RefundResponse])
def all_refunds(refund_status:RefundStatus|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.refunds_read.value))):
    q=db.query(Refund);q=q.filter(Refund.status==refund_status) if refund_status else q;return q.order_by(Refund.requested_at.desc()).all()

@router.get("/{refund_id}",response_model=RefundResponse)
def get_refund(refund_id:UUID,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    r=db.query(Refund).filter(Refund.id==refund_id).first()
    if not r:raise HTTPException(404,"Refund not found")
    if r.requested_by_id!=user.id:raise HTTPException(403,"Not authorized to view this refund")
    return r

@router.post("/{refund_id}/cancel",response_model=RefundResponse)
def cancel(refund_id:UUID,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    r=get_locked(db,refund_id)
    if r.requested_by_id!=user.id:raise HTTPException(403,"Not authorized")
    try:transition_refund(db,r,RefundStatus.cancelled,user_id=user.id,note="Cancelled by buyer");commit(db);db.refresh(r);return r
    except ValueError as exc:db.rollback();raise HTTPException(409,str(exc)) from exc

@router.post("/{refund_id}/review",response_model=RefundResponse)
def review(refund_id:UUID,data:RefundReview,db:Session=Depends(get_db),user:User=Depends(require_permission(PermissionCode.refunds_review.value))):
    r=get_locked(db,refund_id)
    try:transition_refund(db,r,RefundStatus.under_review,user_id=user.id,note=data.note);commit(db);db.refresh(r);return r
    except ValueError as exc:db.rollback();raise HTTPException(409,str(exc)) from exc

@router.post("/{refund_id}/approve",response_model=RefundResponse)
def approve(refund_id:UUID,data:RefundReview,db:Session=Depends(get_db),user:User=Depends(require_permission(PermissionCode.refunds_review.value))):
    r=get_locked(db,refund_id)
    try:transition_refund(db,r,RefundStatus.approved,user_id=user.id,note=data.note);commit(db);db.refresh(r);return r
    except ValueError as exc:db.rollback();raise HTTPException(409,str(exc)) from exc

@router.post("/{refund_id}/reject",response_model=RefundResponse)
def reject(refund_id:UUID,data:RefundReview,db:Session=Depends(get_db),user:User=Depends(require_permission(PermissionCode.refunds_review.value))):
    r=get_locked(db,refund_id)
    try:transition_refund(db,r,RefundStatus.rejected,user_id=user.id,note=data.note);commit(db);db.refresh(r);return r
    except ValueError as exc:db.rollback();raise HTTPException(409,str(exc)) from exc

@router.post("/{refund_id}/process",response_model=RefundResponse)
def process(refund_id:UUID,data:RefundProcess,db:Session=Depends(get_db),user:User=Depends(require_permission(PermissionCode.refunds_process.value))):
    r=get_locked(db,refund_id)
    try:
        if r.status==RefundStatus.approved:transition_refund(db,r,RefundStatus.processing,user_id=user.id,note=data.note,provider_reference=data.provider_reference)
        transition_refund(db,r,RefundStatus.completed,user_id=user.id,note="Refund completed",provider_reference=data.provider_reference)
        if all(x.refund_id==r.id for x in r.items):
            # Mark fully refunded only when all order quantities have been refunded across completed refunds.
            completed={}
            rows=db.query(Refund).filter(Refund.order_id==r.order_id,Refund.status==RefundStatus.completed).all()
            for rr in rows:
                for x in rr.items:completed[x.order_item_id]=completed.get(x.order_item_id,0)+x.quantity
            if all(completed.get(x.id,0)>=x.quantity for x in r.order.items):r.order.status=OrderStatus.refunded
        commit(db);db.refresh(r);return r
    except ValueError as exc:db.rollback();raise HTTPException(409,str(exc)) from exc
