from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from api.enums import PermissionCode
from api.models import SystemSetting, User
from api.permissions import require_permission
from api.schemas import (
    SystemSettingBulkUpdate,
    SystemSettingCreate,
    SystemSettingListResponse,
    SystemSettingResponse,
    SystemSettingUpdate,
)

router = APIRouter(prefix="/settings", tags=["System Settings"])

DEFAULT_SETTINGS = [
    # Platform
    ("platform_name", "Xerin Market", "string", "platform", "Platform display name", True, False),
    ("platform_currency", "TZS", "string", "platform", "Default platform currency", True, False),
    ("platform_country", "Tanzania", "string", "platform", "Default platform country", True, False),
    ("platform_timezone", "Africa/Dar_es_Salaam", "string", "platform", "Default platform timezone", True, False),
    ("maintenance_mode", "false", "boolean", "platform", "Enable maintenance mode", False, False),
    ("registration_enabled", "true", "boolean", "platform", "Allow new user registrations", True, False),
    ("seller_registration_enabled", "true", "boolean", "platform", "Allow new seller registrations", True, False),
    ("max_cart_items", "50", "integer", "platform", "Maximum items in cart", False, False),
    ("order_number_prefix", "XM", "string", "platform", "Order number prefix", False, False),
    # SMS
    ("sms_enabled", "true", "boolean", "sms", "Enable SMS notifications globally", False, False),
    ("sms_provider", "africastalking", "string", "sms", "SMS provider name", False, False),
    ("sms_sender_id", "XERIN", "string", "sms", "SMS sender ID", False, False),
    ("sms_daily_limit", "1000", "integer", "sms", "Maximum SMS per day", False, False),
    ("sms_cost_per_message", "15", "string", "sms", "Cost per SMS in TZS", False, False),
    ("sms_order_notifications", "true", "boolean", "sms", "Send SMS for order events", False, False),
    ("sms_delivery_notifications", "true", "boolean", "sms", "Send SMS for delivery events", False, False),
    ("sms_promotional_enabled", "false", "boolean", "sms", "Send promotional SMS", False, False),
    # Email
    ("email_enabled", "true", "boolean", "email", "Enable email notifications globally", False, False),
    ("email_from_name", "Xerin Market", "string", "email", "From name for outgoing emails", True, False),
    ("email_order_notifications", "true", "boolean", "email", "Send email for order events", False, False),
    ("email_delivery_notifications", "true", "boolean", "email", "Send email for delivery events", False, False),
    ("email_admin_alerts", "true", "boolean", "email", "Send admin alert emails", False, False),
    ("email_promotional_enabled", "true", "boolean", "email", "Send promotional emails", False, False),
    # Mobile App
    ("mobile_app_enabled", "true", "boolean", "mobile", "Enable mobile app access", True, False),
    ("mobile_app_min_version", "1.0.0", "string", "mobile", "Minimum required app version", True, False),
    ("mobile_app_maintenance_message", "App is under maintenance. Please try again later.", "string", "mobile", "Maintenance message for mobile app", True, False),
    ("mobile_app_force_update", "false", "boolean", "mobile", "Force app update on next launch", True, False),
    ("mobile_app_download_url_android", "https://play.google.com/store/apps/details?id=com.xerin.market", "string", "mobile", "Android app download URL", True, False),
    ("mobile_app_download_url_ios", "https://apps.apple.com/app/xerin-market", "string", "mobile", "iOS app download URL", True, False),
    ("mobile_app_api_rate_limit", "100", "integer", "mobile", "API rate limit per minute for mobile", False, False),
    # Delivery
    ("delivery_radius_km", "50", "integer", "delivery", "Default delivery radius in KM", False, False),
    ("delivery_max_weight_kg", "50", "integer", "delivery", "Maximum delivery weight in KG", False, False),
    ("delivery_auto_assign_driver", "false", "boolean", "delivery", "Auto-assign nearest available driver", False, False),
    ("delivery_otp_required", "true", "boolean", "delivery", "Require OTP for delivery confirmation", False, False),
    # Security
    ("security_2fa_required_admin", "true", "boolean", "security", "Require 2FA for admin accounts", False, False),
    ("security_2fa_required_seller", "false", "boolean", "security", "Require 2FA for seller accounts", False, False),
    ("security_session_timeout_minutes", "60", "integer", "security", "Session timeout in minutes", False, False),
    ("security_password_min_length", "8", "integer", "security", "Minimum password length", False, False),
    ("security_max_login_attempts", "5", "integer", "security", "Max login attempts before lockout", False, False),
    ("security_lockout_duration_minutes", "30", "integer", "security", "Account lockout duration in minutes", False, False),
]


@router.get("", response_model=SystemSettingListResponse)
def list_settings(
    category: str | None = Query(None),
    public_only: bool = Query(False),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List system settings. Non-admin users only see public settings."""
    is_admin = current_user.account_type in ("admin", "super_admin")
    q = db.query(SystemSetting)
    if not is_admin or public_only:
        q = q.filter(SystemSetting.is_public.is_(True))
    if category:
        q = q.filter(SystemSetting.category == category)
    if search:
        token = f"%{search.strip()}%"
        q = q.filter(or_(
            cast(SystemSetting.key, String).ilike(token),
            cast(SystemSetting.category, String).ilike(token),
            SystemSetting.description.ilike(token),
        ))
    total = q.count()
    rows = q.order_by(SystemSetting.category, SystemSetting.key).offset((page - 1) * page_size).limit(page_size).all()
    return SystemSettingListResponse(total=total, page=page, page_size=page_size, results=rows)


@router.get("/categories")
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all setting categories."""
    categories = db.query(SystemSetting.category).distinct().all()
    return [c[0] for c in categories]


@router.get("/{key}", response_model=SystemSettingResponse)
def get_setting(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        raise HTTPException(404, f"Setting '{key}' not found")
    if not setting.is_public and current_user.account_type not in ("admin", "super_admin"):
        raise HTTPException(403, "Not authorized to view this setting")
    return setting


@router.post("", response_model=SystemSettingResponse, status_code=status.HTTP_201_CREATED)
def create_setting(
    data: SystemSettingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.settings_manage.value)),
):
    setting = SystemSetting(**data.model_dump(), updated_by_id=current_user.id)
    db.add(setting)
    try:
        db.commit()
        db.refresh(setting)
        return setting
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, f"Setting '{data.key}' already exists") from exc


@router.put("/{key}", response_model=SystemSettingResponse)
def update_setting(
    key: str,
    data: SystemSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.settings_manage.value)),
):
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        raise HTTPException(404, f"Setting '{key}' not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(setting, field, value)
    setting.updated_by_id = current_user.id
    db.commit()
    db.refresh(setting)
    return setting


@router.put("/bulk", response_model=list[SystemSettingResponse])
def bulk_update_settings(
    data: SystemSettingBulkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.settings_manage.value)),
):
    """Update multiple settings at once."""
    results = []
    for key, value in data.settings.items():
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if setting:
            setting.value = value
            setting.updated_by_id = current_user.id
            results.append(setting)
    db.commit()
    for s in results:
        db.refresh(s)
    return results


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_setting(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.settings_manage.value)),
):
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        raise HTTPException(404, f"Setting '{key}' not found")
    db.delete(setting)
    db.commit()


@router.post("/seed")
def seed_default_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.settings_manage.value)),
):
    """Seed default system settings."""
    created = 0
    skipped = 0
    for key, value, data_type, category, description, is_public, is_encrypted in DEFAULT_SETTINGS:
        existing = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if existing:
            skipped += 1
            continue
        db.add(SystemSetting(
            key=key,
            value=value,
            data_type=data_type,
            category=category,
            description=description,
            is_public=is_public,
            is_encrypted=is_encrypted,
            updated_by_id=current_user.id,
        ))
        created += 1
    db.commit()
    return {"created": created, "skipped": skipped, "total": len(DEFAULT_SETTINGS)}
