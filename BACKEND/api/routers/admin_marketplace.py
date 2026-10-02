import json
import uuid
from datetime import datetime
from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import PermissionCode
from api.models import CommissionRule, SystemSetting, User
from api.permissions import require_permission

router = APIRouter(prefix="/admin/marketplace-settings", tags=["Admin Marketplace Settings"])

_SETTINGS_KEY_PREFIX = "marketplace."
_STANDARDS_KEY = "marketplace.domestic_service_standards"

_DEFAULTS = {
    "escrow_release_hours": None,
    "dispute_period_hours": None,
    "seller_release_grace_hours": None,
    "allow_customer_early_acceptance": False,
    "cod_allowed": True,
    "international_delivery_allowed": True,
    "auto_approve_products": False,
    "auto_verify_seller_payout_accounts": False,
}

_BOOL_KEYS = {
    "allow_customer_early_acceptance",
    "cod_allowed",
    "international_delivery_allowed",
    "auto_approve_products",
    "auto_verify_seller_payout_accounts",
}
_NUM_KEYS = {
    "escrow_release_hours",
    "dispute_period_hours",
    "seller_release_grace_hours",
}


def _get_setting(db: Session, key: str) -> SystemSetting | None:
    return db.query(SystemSetting).filter(SystemSetting.key == key).first()


def _set_setting(db: Session, key: str, value: str, data_type: str, user: User | None) -> None:
    row = _get_setting(db, key)
    if row is None:
        row = SystemSetting(key=key, value=value, data_type=data_type, category="marketplace")
        db.add(row)
    else:
        row.value = value
        row.data_type = data_type
    if user is not None:
        row.updated_by_id = user.id


def _read_settings(db: Session) -> dict:
    rows = (
        db.query(SystemSetting)
        .filter(SystemSetting.key.like(f"{_SETTINGS_KEY_PREFIX}%"))
        .all()
    )
    stored = {row.key[len(_SETTINGS_KEY_PREFIX):]: row.value for row in rows}
    configured = bool(stored)

    def num(key: str):
        raw = stored.get(key)
        if raw is None or raw == "":
            return _DEFAULTS[key]
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            return _DEFAULTS[key]

    def flag(key: str):
        raw = stored.get(key)
        if raw is None:
            return _DEFAULTS[key]
        return str(raw).lower() in ("1", "true", "yes", "on")

    out = {"configured": configured, "updated_by_id": None, "created_at": None, "updated_at": None}
    for key in _BOOL_KEYS:
        out[key] = flag(key)
    for key in _NUM_KEYS:
        out[key] = num(key)

    latest = max((r.updated_at or r.created_at for r in rows), default=None)
    out["updated_at"] = latest
    updater = next((r for r in rows if (r.updated_at or r.created_at) == latest), None)
    if updater:
        out["updated_by_id"] = updater.updated_by_id
    return out


@router.get("")
def get_marketplace_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.commissions_read.value)),
):
    return _read_settings(db)


@router.put("")
def put_marketplace_settings(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.commissions_write.value)),
):
    for key, value in payload.items():
        if key not in _BOOL_KEYS and key not in _NUM_KEYS:
            continue
        if key in _BOOL_KEYS:
            _set_setting(db, f"{_SETTINGS_KEY_PREFIX}{key}", "true" if value else "false", "boolean", current_user)
        else:
            _set_setting(
                db,
                f"{_SETTINGS_KEY_PREFIX}{key}",
                "" if value is None else str(value),
                "integer",
                current_user,
            )
    db.commit()
    return _read_settings(db)


# ---------------------------------------------------------------- standards

def _read_standards(db: Session) -> list[dict]:
    row = _get_setting(db, _STANDARDS_KEY)
    if not row or not row.value:
        return []
    try:
        data = json.loads(row.value)
    except (TypeError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _write_standards(db: Session, standards: list[dict], user: User | None) -> None:
    _set_setting(db, _STANDARDS_KEY, json.dumps(standards), "json", user)
    db.commit()


@router.get("/domestic-service-standards")
def list_standards(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.commissions_read.value)),
):
    return _read_standards(db)


@router.post("/domestic-service-standards", status_code=status.HTTP_201_CREATED)
def create_standard(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.commissions_write.value)),
):
    standards = _read_standards(db)
    now = datetime.utcnow().isoformat()
    item = {
        "id": str(uuid.uuid4()),
        "origin_region": payload.get("origin_region", ""),
        "destination_region": payload.get("destination_region", ""),
        "tier": payload.get("tier", "standard"),
        "max_delivery_minutes": int(payload.get("max_delivery_minutes") or 0),
        "is_active": bool(payload.get("is_active", True)),
        "created_at": now,
        "updated_at": now,
    }
    standards.append(item)
    _write_standards(db, standards, current_user)
    return item


@router.patch("/domestic-service-standards/{standard_id}")
def update_standard(
    standard_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.commissions_write.value)),
):
    standards = _read_standards(db)
    for item in standards:
        if item["id"] == standard_id:
            for key in ("origin_region", "destination_region", "tier"):
                if key in payload:
                    item[key] = payload[key]
            if "max_delivery_minutes" in payload:
                item["max_delivery_minutes"] = int(payload["max_delivery_minutes"] or 0)
            if "is_active" in payload:
                item["is_active"] = bool(payload["is_active"])
            item["updated_at"] = datetime.utcnow().isoformat()
            _write_standards(db, standards, current_user)
            return item
    raise HTTPException(status_code=404, detail="Standard not found")


# -------------------------------------------------------------- commission rules

def _rule_out(rule: CommissionRule) -> dict:
    return {
        "id": str(rule.id),
        "name": rule.name,
        "scope": rule.scope.value,
        "rule_type": rule.rule_type.value,
        "rate": float(rule.rate),
        "seller_id": str(rule.seller_id) if rule.seller_id else None,
        "category_id": str(rule.category_id) if rule.category_id else None,
        "product_id": str(rule.product_id) if rule.product_id else None,
        "priority": rule.priority,
        "is_active": rule.is_active,
        "starts_at": rule.starts_at,
        "ends_at": rule.ends_at,
        "created_at": rule.created_at,
    }


@router.get("/commission-rules")
def list_commission_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    scope: str | None = None,
    active: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.commissions_read.value)),
):
    q = db.query(CommissionRule)
    if search:
        q = q.filter(CommissionRule.name.ilike(f"%{search}%"))
    if scope:
        q = q.filter(CommissionRule.scope == scope)
    if active is not None:
        q = q.filter(CommissionRule.is_active.is_(active))

    total = q.with_entities(func.count(CommissionRule.id)).scalar() or 0
    rows = (
        q.order_by(CommissionRule.scope, CommissionRule.priority.desc(), CommissionRule.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, ceil(total / page_size)) if total else 0,
        "results": [_rule_out(r) for r in rows],
    }


@router.post("/commission-rules", status_code=status.HTTP_201_CREATED)
def create_commission_rule(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.commissions_write.value)),
):
    scope = payload.get("scope", "global")
    if payload.get("rule_type") == "percentage" and float(payload.get("rate") or 0) > 100:
        raise HTTPException(status_code=422, detail="Percentage commission cannot exceed 100")

    targets = {
        "seller": payload.get("seller_id"),
        "category": payload.get("category_id"),
        "product": payload.get("product_id"),
    }
    if scope != "global" and not targets.get(scope):
        raise HTTPException(status_code=422, detail=f"{scope}_id is required for this scope")

    rule = CommissionRule(
        name=payload["name"],
        scope=scope,
        rule_type=payload.get("rule_type", "percentage"),
        rate=payload["rate"],
        seller_id=targets.get("seller"),
        category_id=targets.get("category"),
        product_id=targets.get("product"),
        priority=int(payload.get("priority") or 0),
        is_active=bool(payload.get("is_active", True)),
        created_by_id=current_user.id,
    )
    db.add(rule)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflicting commission rule") from exc
    db.refresh(rule)
    return _rule_out(rule)


@router.patch("/commission-rules/{rule_id}")
def update_commission_rule(
    rule_id: UUID,
    payload: dict,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.commissions_write.value)),
):
    rule = db.query(CommissionRule).filter(CommissionRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Commission rule not found")

    for key in ("name", "rate", "priority", "is_active"):
        if key in payload and payload[key] is not None:
            setattr(rule, key, payload[key])

    if rule.rule_type.value == "percentage" and float(rule.rate) > 100:
        raise HTTPException(status_code=422, detail="Percentage commission cannot exceed 100")

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflicting commission rule") from exc
    db.refresh(rule)
    return _rule_out(rule)


@router.delete("/commission-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_commission_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.commissions_write.value)),
):
    rule = db.query(CommissionRule).filter(CommissionRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Commission rule not found")
    db.delete(rule)
    db.commit()
