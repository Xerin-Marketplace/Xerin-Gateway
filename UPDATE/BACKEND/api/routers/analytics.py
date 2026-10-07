from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import PermissionCode
from api.models import User
from api.permissions import require_permission
from api.schemas import AnalyticsOverviewResponse, AnalyticsRankingRow, AnalyticsSeriesPoint, ReconciliationResponse
from api.services.analytics_service import admin_overview, product_rankings, reconciliation, resolve_range, sales_series, seller_overview, seller_rankings

router = APIRouter(prefix="/analytics", tags=["Marketplace Analytics"])


def period(start_at: datetime | None, end_at: datetime | None):
    try:
        return resolve_range(start_at, end_at)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def seller_id_of(user: User):
    if not user.seller_profile:
        raise HTTPException(status_code=403, detail="Seller profile required")
    return user.seller_profile.id


@router.get("/admin/overview", response_model=AnalyticsOverviewResponse)
def admin_dashboard(start_at: datetime | None = None, end_at: datetime | None = None, db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.analytics_admin_read.value))):
    start, end = period(start_at, end_at); return admin_overview(db, start, end)

@router.get("/admin/sales", response_model=list[AnalyticsSeriesPoint])
def admin_sales(start_at: datetime | None = None, end_at: datetime | None = None, db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.analytics_admin_read.value))):
    start, end = period(start_at, end_at); return sales_series(db, start, end)

@router.get("/admin/sellers", response_model=list[AnalyticsRankingRow])
def admin_sellers(start_at: datetime | None = None, end_at: datetime | None = None, limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.analytics_admin_read.value))):
    start, end = period(start_at, end_at); return seller_rankings(db, start, end, limit)

@router.get("/admin/products", response_model=list[AnalyticsRankingRow])
def admin_products(start_at: datetime | None = None, end_at: datetime | None = None, limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.analytics_admin_read.value))):
    start, end = period(start_at, end_at); return product_rankings(db, start, end, limit=limit)

@router.get("/admin/reconciliation", response_model=ReconciliationResponse)
def admin_reconciliation(start_at: datetime | None = None, end_at: datetime | None = None, db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.analytics_admin_read.value))):
    start, end = period(start_at, end_at); return reconciliation(db, start, end)

@router.get("/seller/me/overview", response_model=AnalyticsOverviewResponse)
def my_overview(start_at: datetime | None = None, end_at: datetime | None = None, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.analytics_seller_read.value))):
    start, end = period(start_at, end_at); return seller_overview(db, seller_id_of(current_user), start, end)

@router.get("/seller/me/sales", response_model=list[AnalyticsSeriesPoint])
def my_sales(start_at: datetime | None = None, end_at: datetime | None = None, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.analytics_seller_read.value))):
    start, end = period(start_at, end_at); return sales_series(db, start, end, seller_id_of(current_user))

@router.get("/seller/me/products", response_model=list[AnalyticsRankingRow])
def my_products(start_at: datetime | None = None, end_at: datetime | None = None, limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.analytics_seller_read.value))):
    start, end = period(start_at, end_at); return product_rankings(db, start, end, seller_id=seller_id_of(current_user), limit=limit)
