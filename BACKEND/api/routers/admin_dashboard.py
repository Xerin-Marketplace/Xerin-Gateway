from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from api.deps import get_db
from api.enums import PermissionCode
from api.models import (Order, Seller, Product, User, Payment, Refund, DeliveryJob,
                        NotificationDelivery, SystemAlert, AdminActivityLog)
from api.permissions import require_permission
from api.services.admin_dashboard_service import date_window, summary, status_breakdown, top_searches, most_viewed
from api.services.operations_overview import operations_overview
from api.schemas import OperationsOverviewResponse

router = APIRouter(prefix="/admin/dashboard", tags=["Admin Dashboard"])


@router.get("/operations-overview", response_model=OperationsOverviewResponse)
def dashboard_operations_overview(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(require_permission(PermissionCode.admin_dashboard_operations_read)),
):
    return operations_overview(db, limit=limit)


def _window(period: str, start_at: datetime | None, end_at: datetime | None):
    if start_at and start_at.tzinfo is None: start_at = start_at.replace(tzinfo=timezone.utc)
    if end_at and end_at.tzinfo is None: end_at = end_at.replace(tzinfo=timezone.utc)
    return date_window(period, start_at, end_at)


@router.get("/summary")
def dashboard_summary(period: str = Query("30d", pattern="^(today|7d|30d|custom)$"), start_at: datetime | None = None, end_at: datetime | None = None, db: Session = Depends(get_db), _=Depends(require_permission(PermissionCode.admin_dashboard_read))):
    start, end = _window(period, start_at, end_at); return summary(db, start, end)

@router.get("/sales")
def dashboard_sales(period: str = "30d", start_at: datetime | None = None, end_at: datetime | None = None, db: Session = Depends(get_db), _=Depends(require_permission(PermissionCode.admin_dashboard_finance_read))):
    start,end=_window(period,start_at,end_at); q=db.query(Order).filter(Order.created_at>=start,Order.created_at<=end)
    return {"period":{"start":start,"end":end},"gmv":str(q.with_entities(func.coalesce(func.sum(Order.total),0)).scalar() or 0),"discounts":str(q.with_entities(func.coalesce(func.sum(Order.discount_amount),0)).scalar() or 0),"shipping":str(q.with_entities(func.coalesce(func.sum(Order.shipping_amount),0)).scalar() or 0)}

@router.get("/orders")
def dashboard_orders(period: str="30d", start_at: datetime|None=None, end_at: datetime|None=None, db: Session=Depends(get_db), _=Depends(require_permission(PermissionCode.admin_dashboard_operations_read))):
    start,end=_window(period,start_at,end_at); return {"period":{"start":start,"end":end},"by_status":status_breakdown(db,Order,Order.status,Order.created_at,start,end)}

@router.get("/sellers")
def dashboard_sellers(db: Session=Depends(get_db), _=Depends(require_permission(PermissionCode.admin_dashboard_operations_read))):
    return {"total":db.query(Seller).count(),"approved":db.query(Seller).filter(Seller.status=="approved").count(),"pending":db.query(Seller).filter(Seller.status.in_(["pending","under_review"])).count()}

@router.get("/products")
def dashboard_products(db: Session=Depends(get_db), _=Depends(require_permission(PermissionCode.admin_dashboard_operations_read))):
    return {"total":db.query(Product).count(),"approved":db.query(Product).filter(Product.status=="approved").count(),"pending_review":db.query(Product).filter(Product.status=="pending_review").count()}

@router.get("/customers")
def dashboard_customers(db: Session=Depends(get_db), _=Depends(require_permission(PermissionCode.admin_dashboard_read))): return {"total":db.query(User).count(),"verified":db.query(User).filter(User.is_verified.is_(True)).count()}

@router.get("/payments")
def dashboard_payments(db: Session=Depends(get_db), _=Depends(require_permission(PermissionCode.admin_dashboard_finance_read))): return {"total":db.query(Payment).count(),"failed":db.query(Payment).filter(Payment.status=="failed").count(),"successful":db.query(Payment).filter(Payment.status=="completed").count()}

@router.get("/refunds")
def dashboard_refunds(db: Session=Depends(get_db), _=Depends(require_permission(PermissionCode.admin_dashboard_finance_read))): return {"total":db.query(Refund).count(),"pending":db.query(Refund).filter(Refund.status.in_(["requested","under_review","approved"])).count()}

@router.get("/delivery")
def dashboard_delivery(db: Session=Depends(get_db), _=Depends(require_permission(PermissionCode.admin_dashboard_operations_read))): return {"total":db.query(DeliveryJob).count(),"failed":db.query(DeliveryJob).filter(DeliveryJob.status=="delivery_failed").count()}

@router.get("/notifications")
def dashboard_notifications(db: Session=Depends(get_db), _=Depends(require_permission(PermissionCode.admin_dashboard_operations_read))): return {"total":db.query(NotificationDelivery).count(),"failed":db.query(NotificationDelivery).filter(NotificationDelivery.status=="failed").count()}

@router.get("/search")
def dashboard_search(limit:int=Query(10,ge=1,le=50), db: Session=Depends(get_db), _=Depends(require_permission(PermissionCode.admin_dashboard_read))): return {"top_searches":top_searches(db,limit),"most_viewed_products":most_viewed(db,limit)}

@router.get("/alerts")
def dashboard_alerts(resolved:bool|None=None, limit:int=Query(50,ge=1,le=200), db: Session=Depends(get_db), _=Depends(require_permission(PermissionCode.admin_dashboard_security_read))):
    q=db.query(SystemAlert); q=q.filter(SystemAlert.is_resolved==resolved) if resolved is not None else q
    return [{"id":str(a.id),"type":a.alert_type,"severity":a.severity,"title":a.title,"message":a.message,"resolved":a.is_resolved,"created_at":a.created_at} for a in q.order_by(SystemAlert.created_at.desc()).limit(limit).all()]

@router.patch("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id:UUID, db:Session=Depends(get_db), current_user=Depends(require_permission(PermissionCode.admin_system_alerts_manage))):
    alert=db.query(SystemAlert).filter(SystemAlert.id==alert_id).first()
    if not alert: raise HTTPException(status_code=404,detail="System alert not found")
    alert.is_resolved=True; alert.resolved_by_id=current_user.id; alert.resolved_at=datetime.now(timezone.utc)
    db.add(AdminActivityLog(admin_user_id=current_user.id,action="resolve_system_alert",resource_type="system_alert",resource_id=str(alert.id)))
    db.commit(); return {"message":"System alert resolved","id":str(alert.id)}

@router.get("/activity-logs")
def dashboard_activity_logs(limit:int=Query(100,ge=1,le=500), db:Session=Depends(get_db), _=Depends(require_permission(PermissionCode.admin_activity_logs_read))):
    return [{"id":str(x.id),"admin_user_id":str(x.admin_user_id) if x.admin_user_id else None,"action":x.action,"resource_type":x.resource_type,"resource_id":x.resource_id,"details":x.details,"created_at":x.created_at} for x in db.query(AdminActivityLog).order_by(AdminActivityLog.created_at.desc()).limit(limit).all()]
