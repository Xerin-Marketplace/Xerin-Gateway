"""Admin finance endpoints.

The full payment-provider/currency/FX modules are not present in this
branch. These endpoints return honest empty data (or the single supported
currency) so the admin finance UI renders cleanly instead of 404ing.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import PermissionCode
from api.permissions import require_permission

router = APIRouter(prefix="/admin", tags=["Admin Finance"])

TZS_CURRENCY = {
    "id": "tzs",
    "code": "TZS",
    "name": "Tanzanian Shilling",
    "symbol": "TSh",
    "is_base": True,
    "is_active": True,
    "decimal_places": 0,
}


@router.get("/currencies")
def list_currencies(
    _=Depends(require_permission(PermissionCode.admin_dashboard_finance_read.value)),
):
    return [TZS_CURRENCY]


@router.post("/currencies", status_code=501)
def create_currency(
    _=Depends(require_permission(PermissionCode.admin_dashboard_finance_read.value)),
):
    raise HTTPException(501, "Currency management is not available on this deployment")


@router.get("/fx-rates")
def list_fx_rates(
    _=Depends(require_permission(PermissionCode.admin_dashboard_finance_read.value)),
):
    return []


@router.get("/payment-providers")
def list_payment_providers(
    _=Depends(require_permission(PermissionCode.admin_dashboard_finance_read.value)),
):
    return []


@router.get("/payouts")
def list_payouts(
    _=Depends(require_permission(PermissionCode.admin_dashboard_finance_read.value)),
):
    return []


@router.get("/payment-disputes")
def list_payment_disputes(
    _=Depends(require_permission(PermissionCode.admin_dashboard_finance_read.value)),
):
    return []


@router.get("/payment-risk-events")
def list_payment_risk_events(
    _=Depends(require_permission(PermissionCode.admin_dashboard_finance_read.value)),
):
    return []


@router.get("/reconciliation")
def list_reconciliation(
    _=Depends(require_permission(PermissionCode.admin_dashboard_finance_read.value)),
):
    return []


@router.get("/payments/dashboard")
def payments_dashboard(
    _=Depends(require_permission(PermissionCode.admin_dashboard_finance_read.value)),
):
    return {
        "processed_volume": 0,
        "successful_payments": 0,
        "pending_payments": 0,
        "failed_payments": 0,
        "refunded_amount": 0,
        "pending_payouts": 0,
        "completed_payouts": 0,
        "platform_commission": 0,
        "seller_earnings": 0,
        "currency": "TZS",
    }
