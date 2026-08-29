from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import mimetypes
import secrets
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from api.countries import country_options
from api.deps import get_current_user, get_db
from api.enums import (
    LogisticsCompanyStatus,
    LogisticsCompanyPermission,
    LogisticsDocumentType,
    LogisticsDocumentStatus,
    LogisticsMemberRole,
    MultiSellerPricingStrategy,
    LogisticsScope,
    PermissionCode,
    ShipmentStatus,
    PickupJobStatus,
    NotificationEvent,
)
from api.models import (
    LogisticsCompany,
    LogisticsCompanyDocument,
    LogisticsCompanyUser,
    LogisticsIntegrationConfig,
    LogisticsPayoutAccount,
    LogisticsWebhookEvent,
    LogisticsPickupJob,
    Seller,
    SellerOrder,
    SellerOrderMessage,
    SellerOrderMessageAttachment,
    Shipment,
    ShipmentHandover,
    ShipmentPickupProof,
    ShipmentTrackingEvent,
    ShippingMethod,
    ShippingRate,
    ShippingZone,
    User,
    UserRole,
    Role,
    UserStatus,
)
from api.permissions import get_user_permissions, require_permission
from api.services.seller_handover import ensure_shipment_handover
from api.services.notification_service import notification_service
from api.services.pickup_proof_service import (
    PickupProofError,
    create_pickup_proof,
    store_pickup_proof_image,
)
from api.schemas import (
    LogisticsCompanyCreate,
    LogisticsCompanyOnboardCreate,
    LogisticsCompanyOnboardResponse,
    LogisticsCredentialsEmailResponse,
    LogisticsOnboardingStatusResponse,
    PaginatedLogisticsOnboardingResponse,
    LogisticsOnboardingReviewRequest,
    LogisticsDocumentResponse,
    PaginatedLogisticsDocumentResponse,
    LogisticsDocumentReviewRequest,
    LogisticsDocumentRequirementsResponse,
    LogisticsCompanyAccountResponse,
    LogisticsCompanyProfileUpdate,
    LogisticsCompanyResponse,
    LogisticsCompanyUpdate,
    LogisticsCompanyUserCreate,
    LogisticsCompanyUserUpdate,
    LogisticsCompanyUserResponse,
    LogisticsCompanyMemberResponse,
    LogisticsIntegrationCreate,
    LogisticsIntegrationResponse,
    LogisticsIntegrationUpdate,
    LogisticsDashboardResponse,
    LogisticsWebhookEventResponse,
    PaginatedLogisticsWebhookEventResponse,
    LogisticsCourierArrivalRequest,
    LogisticsPickupJobAssign,
    LogisticsPickupJobCreate,
    LogisticsPickupJobResponse,
    LogisticsPickupJobStatusUpdate,
    PaginatedLogisticsPickupJobResponse,
    LogisticsPricingSettingsResponse,
    LogisticsPricingSettingsUpdate,
    PaginatedLogisticsCompanyResponse,
    PaginatedShipmentResponse,
    PaginatedShippingMethodResponse,
    PaginatedShippingRateResponse,
    PaginatedShippingZoneResponse,
    ShipmentResponse,
    ShipmentHandoverResponse,
    SellerOrderMessageCreate,
    SellerOrderMessageResponse,
    PickupProofResponse,
    ShipmentTrackingEventCreate,
    ShippingMethodCreate,
    ShippingMethodResponse,
    ShippingMethodUpdate,
    ShippingRateCreate,
    ShippingRateResponse,
    ShippingZoneCreate,
    ShippingZoneResponse,
    ShippingZoneUpdate,
)
from api.security import hash_password
from api.routers.email import send_email
from api.config import settings

router = APIRouter(prefix="/logistics", tags=["Logistics"])


@router.get("/country-options")
def logistics_country_options(_: User = Depends(get_current_user)):
    """Canonical country choices for logistics coverage zones."""
    return country_options()


def _generate_temporary_password(length: int = 16) -> str:
    """Generate a bcrypt-safe password with each required character class."""
    upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    lower = "abcdefghijkmnopqrstuvwxyz"
    digits = "23456789"
    symbols = "!@#$%*-_"
    chars = [
        secrets.choice(upper), secrets.choice(lower),
        secrets.choice(digits), secrets.choice(symbols),
    ]
    alphabet = upper + lower + digits + symbols
    chars.extend(secrets.choice(alphabet) for _ in range(length - len(chars)))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def _send_logistics_credentials_email(*, email: str, recipient_name: str, company_name: str, temporary_password: str) -> None:
    login_url = settings.LOGISTICS_PORTAL_LOGIN_URL
    body = (
        f"Hello {recipient_name},\n\n"
        f"Welcome to Xerin Marketplace. {company_name} has been registered and you are its primary logistics administrator.\n\n"
        f"Login page: {login_url}\n"
        f"Email: {email}\n"
        f"Temporary password: {temporary_password}\n\n"
        "For security, sign in and change this temporary password immediately. "
        "Then complete the company profile, delivery zones, services, charges and payout account. "
        "API and webhook setup is optional and may be skipped for now.\n\n"
        "Your company will remain pending until onboarding is reviewed."
    )
    send_email(to=email, subject=f"Your Xerin Logistics login – {company_name}", body=body)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Logistics record conflicts with existing data",
        ) from exc


def _pages(total: int, page_size: int) -> int:
    return 0 if total == 0 else (total + page_size - 1) // page_size


def _membership_for_user(db: Session, user_id: UUID) -> LogisticsCompanyUser | None:
    return (
        db.query(LogisticsCompanyUser)
        .options(joinedload(LogisticsCompanyUser.company))
        .filter(
            LogisticsCompanyUser.user_id == user_id,
            LogisticsCompanyUser.is_active.is_(True),
        )
        .first()
    )


_ROLE_PERMISSIONS: dict[LogisticsMemberRole, set[LogisticsCompanyPermission]] = {
    LogisticsMemberRole.company_admin: set(LogisticsCompanyPermission),
    LogisticsMemberRole.operations_manager: {
        LogisticsCompanyPermission.profile_manage,
        LogisticsCompanyPermission.zones_manage,
        LogisticsCompanyPermission.rates_manage,
        LogisticsCompanyPermission.pickups_manage,
        LogisticsCompanyPermission.shipments_manage,
        LogisticsCompanyPermission.dashboard_read,
    },
    LogisticsMemberRole.dispatcher: {
        LogisticsCompanyPermission.pickups_manage,
        LogisticsCompanyPermission.shipments_manage,
        LogisticsCompanyPermission.dashboard_read,
    },
    LogisticsMemberRole.driver: {LogisticsCompanyPermission.shipments_manage},
    LogisticsMemberRole.viewer: {LogisticsCompanyPermission.dashboard_read},
}


def _effective_company_permissions(
    membership: LogisticsCompanyUser,
) -> set[LogisticsCompanyPermission]:
    if membership.is_primary_contact:
        return set(LogisticsCompanyPermission)

    permissions = set(_ROLE_PERMISSIONS.get(membership.member_role, set()))
    for value in membership.permissions_json or []:
        try:
            permissions.add(LogisticsCompanyPermission(value))
        except ValueError:
            continue
    return permissions


def _require_company_permission(
    membership: LogisticsCompanyUser,
    permission: LogisticsCompanyPermission,
) -> None:
    if permission not in _effective_company_permissions(membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Company permission denied. Required: {permission.value}",
        )


def _member_response(membership: LogisticsCompanyUser) -> dict:
    return {
        "id": membership.id,
        "logistics_company_id": membership.logistics_company_id,
        "user_id": membership.user_id,
        "title": membership.title,
        "member_role": membership.member_role,
        "permissions_json": membership.permissions_json or [],
        "is_primary_contact": membership.is_primary_contact,
        "is_active": membership.is_active,
        "created_at": membership.created_at,
        "first_name": membership.user.first_name,
        "last_name": membership.user.last_name,
        "email": membership.user.email,
        "effective_permissions": sorted(
            _effective_company_permissions(membership), key=lambda item: item.value
        ),
    }


    
# Companies
    
@router.get(
    "/companies",
    response_model=PaginatedLogisticsCompanyResponse,
)
def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=150),
    status_filter: LogisticsCompanyStatus | None = Query(None, alias="status"),
    scope: LogisticsScope | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_companies_read.value)
    ),
):
    query = db.query(LogisticsCompany)

    if status_filter:
        query = query.filter(LogisticsCompany.status == status_filter)
    if scope:
        query = query.filter(LogisticsCompany.scope == scope)

    term = (search or "").strip()
    if term:
        pattern = f"%{term}%"
        query = query.filter(
            or_(
                LogisticsCompany.name.ilike(pattern),
                LogisticsCompany.code.ilike(pattern),
                LogisticsCompany.contact_name.ilike(pattern),
                LogisticsCompany.contact_email.ilike(pattern),
                LogisticsCompany.contact_phone.ilike(pattern),
            )
        )

    total = query.count()
    rows = (
        query.order_by(LogisticsCompany.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": _pages(total, page_size),
        "results": rows,
    }


@router.post(
    "/companies",
    response_model=LogisticsCompanyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_company(
    data: LogisticsCompanyCreate,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_companies_manage.value)
    ),
):
    company = LogisticsCompany(**data.model_dump())
    db.add(company)
    _commit(db)
    db.refresh(company)
    return company


@router.post(
    "/companies/onboard",
    response_model=LogisticsCompanyOnboardResponse,
    status_code=status.HTTP_201_CREATED,
)
def onboard_company(
    data: LogisticsCompanyOnboardCreate,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_companies_manage.value)
    ),
):
    """Create company, first user, role and primary membership atomically."""
    email = str(data.administrator.email).strip().lower()
    phone = (data.administrator.phone or "").strip() or None

    if db.query(User.id).filter(func.lower(User.email) == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Administrator email already exists")
    if phone and db.query(User.id).filter(User.phone == phone).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Administrator phone already exists")
    if db.query(LogisticsCompany.id).filter(
        or_(
            func.lower(LogisticsCompany.name) == data.company.name.strip().lower(),
            func.lower(LogisticsCompany.code) == data.company.code.strip().lower(),
        )
    ).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Logistics company name or code already exists")

    company_values = data.company.model_dump()
    company_values["status"] = LogisticsCompanyStatus.pending
    company_values["metadata_json"] = {
        **(company_values.get("metadata_json") or {}),
        "onboarding": {
            "state": "invited",
            "webhook_optional": True,
            "created_by_admin": True,
        },
    }
    company = LogisticsCompany(**company_values)
    temporary_password = _generate_temporary_password()
    user = User(
        first_name=data.administrator.first_name.strip(),
        last_name=data.administrator.last_name.strip(),
        email=email,
        phone=phone,
        password_hash=hash_password(temporary_password),
        status=UserStatus.active,
        is_verified=True,
    )
    try:
        role = db.query(Role).filter(Role.name == "company_admin").first()
        if role is None:
            role = Role(
                name="company_admin",
                description="Primary administrator of a logistics company",
            )
            db.add(role)
            db.flush()
        db.add_all([company, user])
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        membership = LogisticsCompanyUser(
            logistics_company_id=company.id,
            user_id=user.id,
            title="Company Administrator",
            member_role=LogisticsMemberRole.company_admin,
            permissions_json=[],
            is_primary_contact=True,
            is_active=True,
        )
        db.add(membership)
        db.flush()
        company_id = company.id
        user_id = user.id
        membership_id = membership.id
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Company, administrator or membership conflicts with existing data",
        ) from exc
    except Exception:
        db.rollback()
        raise

    company = db.get(LogisticsCompany, company_id)
    email_sent = False
    warning = None
    try:
        recipient_name = f"{data.administrator.first_name} {data.administrator.last_name}".strip()
        _send_logistics_credentials_email(
            email=email, recipient_name=recipient_name, company_name=company.name,
            temporary_password=temporary_password,
        )
        email_sent = True
    except Exception:
        # SMTP must not roll back the already-committed company account.
        warning = "Account created, but the welcome email could not be delivered"

    return {
        "company": company,
        "administrator_user_id": user_id,
        "membership_id": membership_id,
        "welcome_email_sent": email_sent,
        "warning": warning,
    }


@router.post(
    "/companies/{company_id}/administrator/resend-credentials",
    response_model=LogisticsCredentialsEmailResponse,
)
def resend_company_administrator_credentials(
    company_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.logistics_companies_manage.value)),
):
    company = db.get(LogisticsCompany, company_id)
    if not company:
        raise HTTPException(404, "Logistics company not found")
    membership = (
        db.query(LogisticsCompanyUser)
        .options(joinedload(LogisticsCompanyUser.user))
        .filter(
            LogisticsCompanyUser.logistics_company_id == company_id,
            LogisticsCompanyUser.is_primary_contact.is_(True),
            LogisticsCompanyUser.is_active.is_(True),
        )
        .first()
    )
    if not membership or not membership.user:
        raise HTTPException(404, "Primary logistics administrator not found")
    administrator = membership.user
    temporary_password = _generate_temporary_password()
    recipient_name = f"{administrator.first_name or ''} {administrator.last_name or ''}".strip() or company.name
    try:
        _send_logistics_credentials_email(
            email=administrator.email,
            recipient_name=recipient_name,
            company_name=company.name,
            temporary_password=temporary_password,
        )
    except Exception as exc:
        raise HTTPException(502, "Credentials email could not be delivered; the existing password was preserved") from exc
    administrator.password_hash = hash_password(temporary_password)
    _commit(db)
    return {
        "company_id": company.id,
        "administrator_user_id": administrator.id,
        "email": administrator.email,
        "credentials_email_sent": True,
        "message": "A new temporary password was generated and emailed to the primary administrator",
    }


@router.get("/companies/{company_id}", response_model=LogisticsCompanyResponse)
def get_company(
    company_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_companies_read.value)
    ),
):
    company = db.get(LogisticsCompany, company_id)
    if not company:
        raise HTTPException(404, "Logistics company not found")
    return company


@router.patch("/companies/{company_id}", response_model=LogisticsCompanyResponse)
def update_company(
    company_id: UUID,
    data: LogisticsCompanyUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_companies_manage.value)
    ),
):
    company = db.get(LogisticsCompany, company_id)
    if not company:
        raise HTTPException(404, "Logistics company not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(company, key, value)

    _commit(db)
    db.refresh(company)
    return company


@router.delete("/companies/{company_id}")
def deactivate_company(
    company_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_companies_manage.value)
    ),
):
    company = db.get(LogisticsCompany, company_id)
    if not company:
        raise HTTPException(404, "Logistics company not found")

    company.status = LogisticsCompanyStatus.inactive
    _commit(db)
    return {"message": "Logistics company deactivated"}


    
# Company users. These are normal RBAC users linked to an organization.
    
@router.get(
    "/companies/{company_id}/users",
    response_model=list[LogisticsCompanyUserResponse],
)
def list_company_users(
    company_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_companies_read.value)
    ),
):
    if not db.get(LogisticsCompany, company_id):
        raise HTTPException(404, "Logistics company not found")

    return (
        db.query(LogisticsCompanyUser)
        .filter(LogisticsCompanyUser.logistics_company_id == company_id)
        .order_by(LogisticsCompanyUser.created_at.asc())
        .all()
    )


@router.post(
    "/companies/{company_id}/users",
    response_model=LogisticsCompanyUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def attach_company_user(
    company_id: UUID,
    data: LogisticsCompanyUserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_companies_manage.value)
    ),
):
    if not db.get(LogisticsCompany, company_id):
        raise HTTPException(404, "Logistics company not found")
    if not db.get(User, data.user_id):
        raise HTTPException(404, "User not found")
    existing_membership = (
        db.query(LogisticsCompanyUser)
        .filter(LogisticsCompanyUser.user_id == data.user_id)
        .first()
    )
    if existing_membership:
        raise HTTPException(409, "User is already linked to a logistics company")

    membership = LogisticsCompanyUser(
        logistics_company_id=company_id,
        **data.model_dump(),
    )
    db.add(membership)
    _commit(db)
    db.refresh(membership)
    return membership


@router.patch(
    "/companies/{company_id}/users/{user_id}",
    response_model=LogisticsCompanyUserResponse,
)
def update_company_user(
    company_id: UUID,
    user_id: UUID,
    data: LogisticsCompanyUserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_companies_manage.value)
    ),
):
    membership = (
        db.query(LogisticsCompanyUser)
        .filter(
            LogisticsCompanyUser.logistics_company_id == company_id,
            LogisticsCompanyUser.user_id == user_id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(404, "Logistics company user membership not found")

    changes = data.model_dump(exclude_unset=True)
    if membership.is_primary_contact and changes.get("is_primary_contact") is False:
        other_primary = (
            db.query(LogisticsCompanyUser)
            .filter(
                LogisticsCompanyUser.logistics_company_id == company_id,
                LogisticsCompanyUser.id != membership.id,
                LogisticsCompanyUser.is_primary_contact.is_(True),
                LogisticsCompanyUser.is_active.is_(True),
            )
            .first()
        )
        if not other_primary:
            raise HTTPException(409, "Assign another active primary contact first")

    for key, value in changes.items():
        setattr(membership, key, value)
    _commit(db)
    db.refresh(membership)
    return membership


@router.delete("/companies/{company_id}/users/{user_id}")
def detach_company_user(
    company_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_companies_manage.value)
    ),
):
    membership = (
        db.query(LogisticsCompanyUser)
        .filter(
            LogisticsCompanyUser.logistics_company_id == company_id,
            LogisticsCompanyUser.user_id == user_id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(404, "Logistics company user membership not found")

    if membership.is_primary_contact and membership.is_active:
        other_primary = (
            db.query(LogisticsCompanyUser)
            .filter(
                LogisticsCompanyUser.logistics_company_id == company_id,
                LogisticsCompanyUser.id != membership.id,
                LogisticsCompanyUser.is_primary_contact.is_(True),
                LogisticsCompanyUser.is_active.is_(True),
            )
            .first()
        )
        if not other_primary:
            raise HTTPException(409, "Assign another active primary contact first")

    db.delete(membership)
    _commit(db)
    return {"message": "User removed from logistics company"}


@router.get("/me/users", response_model=list[LogisticsCompanyMemberResponse])
def my_company_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")

    rows = (
        db.query(LogisticsCompanyUser)
        .options(joinedload(LogisticsCompanyUser.user))
        .filter(
            LogisticsCompanyUser.logistics_company_id
            == membership.logistics_company_id
        )
        .order_by(
            LogisticsCompanyUser.is_primary_contact.desc(),
            LogisticsCompanyUser.created_at.asc(),
        )
        .all()
    )
    return [_member_response(row) for row in rows]


@router.post(
    "/me/users",
    response_model=LogisticsCompanyMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_my_company_user(
    data: LogisticsCompanyUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_membership = _membership_for_user(db, current_user.id)
    if not current_membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(
        current_membership, LogisticsCompanyPermission.users_manage
    )
    if data.is_primary_contact and not current_membership.is_primary_contact:
        raise HTTPException(403, "Only the primary contact may assign another primary contact")

    user = db.get(User, data.user_id)
    if not user:
        raise HTTPException(404, "User not found")
    existing_membership = (
        db.query(LogisticsCompanyUser)
        .filter(LogisticsCompanyUser.user_id == data.user_id)
        .first()
    )
    if existing_membership:
        raise HTTPException(409, "User is already linked to a logistics company")
    membership = LogisticsCompanyUser(
        logistics_company_id=current_membership.logistics_company_id,
        **data.model_dump(),
    )
    db.add(membership)
    _commit(db)
    db.refresh(membership)
    membership.user = user
    return _member_response(membership)


@router.patch(
    "/me/users/{user_id}", response_model=LogisticsCompanyMemberResponse
)
def update_my_company_user(
    user_id: UUID,
    data: LogisticsCompanyUserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_membership = _membership_for_user(db, current_user.id)
    if not current_membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(
        current_membership, LogisticsCompanyPermission.users_manage
    )

    target = (
        db.query(LogisticsCompanyUser)
        .options(joinedload(LogisticsCompanyUser.user))
        .filter(
            LogisticsCompanyUser.logistics_company_id
            == current_membership.logistics_company_id,
            LogisticsCompanyUser.user_id == user_id,
        )
        .first()
    )
    if not target:
        raise HTTPException(404, "Logistics company user membership not found")

    changes = data.model_dump(exclude_unset=True)
    if "is_primary_contact" in changes and not current_membership.is_primary_contact:
        raise HTTPException(403, "Only the primary contact may change the primary contact")
    if target.is_primary_contact and (
        changes.get("is_primary_contact") is False
        or changes.get("is_active") is False
    ):
        other_primary = (
            db.query(LogisticsCompanyUser)
            .filter(
                LogisticsCompanyUser.logistics_company_id
                == current_membership.logistics_company_id,
                LogisticsCompanyUser.id != target.id,
                LogisticsCompanyUser.is_primary_contact.is_(True),
                LogisticsCompanyUser.is_active.is_(True),
            )
            .first()
        )
        if not other_primary:
            raise HTTPException(409, "Assign another active primary contact first")

    for key, value in changes.items():
        setattr(target, key, value)
    _commit(db)
    db.refresh(target)
    return _member_response(target)


@router.delete("/me/users/{user_id}")
def remove_my_company_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_membership = _membership_for_user(db, current_user.id)
    if not current_membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(
        current_membership, LogisticsCompanyPermission.users_manage
    )

    target = (
        db.query(LogisticsCompanyUser)
        .filter(
            LogisticsCompanyUser.logistics_company_id
            == current_membership.logistics_company_id,
            LogisticsCompanyUser.user_id == user_id,
        )
        .first()
    )
    if not target:
        raise HTTPException(404, "Logistics company user membership not found")
    if target.is_primary_contact and target.is_active:
        other_primary = (
            db.query(LogisticsCompanyUser)
            .filter(
                LogisticsCompanyUser.logistics_company_id
                == current_membership.logistics_company_id,
                LogisticsCompanyUser.id != target.id,
                LogisticsCompanyUser.is_primary_contact.is_(True),
                LogisticsCompanyUser.is_active.is_(True),
            )
            .first()
        )
        if not other_primary:
            raise HTTPException(409, "Assign another active primary contact first")

    db.delete(target)
    _commit(db)
    return {"message": "User removed from logistics company"}


    
# Services
    
@router.get("/services", response_model=PaginatedShippingMethodResponse)
def list_services(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=150),
    company_id: UUID | None = Query(None),
    scope: LogisticsScope | None = Query(None),
    active: bool | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_services_read.value)
    ),
):
    query = db.query(ShippingMethod)

    if company_id:
        query = query.filter(ShippingMethod.logistics_company_id == company_id)
    if scope:
        query = query.filter(ShippingMethod.scope == scope)
    if active is not None:
        query = query.filter(ShippingMethod.is_active.is_(active))

    term = (search or "").strip()
    if term:
        pattern = f"%{term}%"
        query = query.filter(
            or_(
                ShippingMethod.name.ilike(pattern),
                ShippingMethod.service_code.ilike(pattern),
                ShippingMethod.carrier_name.ilike(pattern),
                ShippingMethod.description.ilike(pattern),
            )
        )

    total = query.count()
    rows = (
        query.order_by(ShippingMethod.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": _pages(total, page_size),
        "results": rows,
    }


@router.post("/services", response_model=ShippingMethodResponse, status_code=201)
def create_service(
    data: ShippingMethodCreate,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_services_manage.value)
    ),
):
    if data.logistics_company_id:
        company = db.get(LogisticsCompany, data.logistics_company_id)
        if not company:
            raise HTTPException(404, "Logistics company not found")

    service = ShippingMethod(**data.model_dump())
    if data.logistics_company_id:
        service.carrier_name = service.carrier_name or company.name

    db.add(service)
    _commit(db)
    db.refresh(service)
    return service


@router.patch("/services/{service_id}", response_model=ShippingMethodResponse)
def update_service(
    service_id: UUID,
    data: ShippingMethodUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_services_manage.value)
    ),
):
    service = db.get(ShippingMethod, service_id)
    if not service:
        raise HTTPException(404, "Logistics service not found")

    update_data = data.model_dump(exclude_unset=True)
    company_id = update_data.get("logistics_company_id")
    if company_id and not db.get(LogisticsCompany, company_id):
        raise HTTPException(404, "Logistics company not found")

    for key, value in update_data.items():
        setattr(service, key, value)

    _commit(db)
    db.refresh(service)
    return service


@router.delete("/services/{service_id}")
def deactivate_service(
    service_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_services_manage.value)
    ),
):
    service = db.get(ShippingMethod, service_id)
    if not service:
        raise HTTPException(404, "Logistics service not found")
    service.is_active = False
    _commit(db)
    return {"message": "Logistics service deactivated"}


    
# Zones
    
@router.get("/zones", response_model=PaginatedShippingZoneResponse)
def list_zones(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=150),
    company_id: UUID | None = Query(None),
    scope: LogisticsScope | None = Query(None),
    active: bool | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_zones_read.value)
    ),
):
    query = db.query(ShippingZone)
    if company_id:
        query = query.filter(ShippingZone.logistics_company_id == company_id)
    if scope:
        query = query.filter(ShippingZone.scope == scope)
    if active is not None:
        query = query.filter(ShippingZone.is_active.is_(active))

    term = (search or "").strip()
    if term:
        pattern = f"%{term}%"
        query = query.filter(
            or_(
                ShippingZone.name.ilike(pattern),
                ShippingZone.country.ilike(pattern),
            )
        )

    total = query.count()
    rows = (
        query.order_by(ShippingZone.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": _pages(total, page_size),
        "results": rows,
    }


@router.post("/zones", response_model=ShippingZoneResponse, status_code=201)
def create_zone(
    data: ShippingZoneCreate,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_zones_manage.value)
    ),
):
    if data.logistics_company_id and not db.get(
        LogisticsCompany, data.logistics_company_id
    ):
        raise HTTPException(404, "Logistics company not found")
    zone = ShippingZone(**data.model_dump())
    db.add(zone)
    _commit(db)
    db.refresh(zone)
    return zone


@router.patch("/zones/{zone_id}", response_model=ShippingZoneResponse)
def update_zone(
    zone_id: UUID,
    data: ShippingZoneUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_zones_manage.value)
    ),
):
    zone = db.get(ShippingZone, zone_id)
    if not zone:
        raise HTTPException(404, "Shipping zone not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(zone, key, value)
    _commit(db)
    db.refresh(zone)
    return zone


@router.delete("/zones/{zone_id}")
def deactivate_zone(
    zone_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_zones_manage.value)
    ),
):
    zone = db.get(ShippingZone, zone_id)
    if not zone:
        raise HTTPException(404, "Shipping zone not found")
    zone.is_active = False
    _commit(db)
    return {"message": "Shipping zone deactivated"}


@router.get("/me/zones", response_model=PaginatedShippingZoneResponse)
def my_company_zones(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=150),
    active: bool | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")

    query = db.query(ShippingZone).filter(
        ShippingZone.logistics_company_id == membership.logistics_company_id
    )
    if active is not None:
        query = query.filter(ShippingZone.is_active.is_(active))
    term = (search or "").strip()
    if term:
        pattern = f"%{term}%"
        query = query.filter(
            or_(
                ShippingZone.name.ilike(pattern),
                ShippingZone.country.ilike(pattern),
            )
        )

    total = query.count()
    rows = (
        query.order_by(ShippingZone.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": _pages(total, page_size),
        "results": rows,
    }


@router.post(
    "/me/zones",
    response_model=ShippingZoneResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_my_company_zone(
    data: ShippingZoneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(
        membership, LogisticsCompanyPermission.zones_manage
    )
    if data.logistics_company_id not in (None, membership.logistics_company_id):
        raise HTTPException(403, "Cannot create a zone for another company")

    values = data.model_dump(exclude={"logistics_company_id"})
    zone = ShippingZone(
        logistics_company_id=membership.logistics_company_id,
        **values,
    )
    db.add(zone)
    _commit(db)
    db.refresh(zone)
    return zone


@router.get("/me/zones/{zone_id}", response_model=ShippingZoneResponse)
def get_my_company_zone(
    zone_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    zone = (
        db.query(ShippingZone)
        .filter(
            ShippingZone.id == zone_id,
            ShippingZone.logistics_company_id == membership.logistics_company_id,
        )
        .first()
    )
    if not zone:
        raise HTTPException(404, "Shipping zone not found")
    return zone


@router.patch("/me/zones/{zone_id}", response_model=ShippingZoneResponse)
def update_my_company_zone(
    zone_id: UUID,
    data: ShippingZoneUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(
        membership, LogisticsCompanyPermission.zones_manage
    )
    zone = (
        db.query(ShippingZone)
        .filter(
            ShippingZone.id == zone_id,
            ShippingZone.logistics_company_id == membership.logistics_company_id,
        )
        .first()
    )
    if not zone:
        raise HTTPException(404, "Shipping zone not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(zone, key, value)
    if not zone.covers_entire_country and not any(
        (
            zone.regions,
            zone.cities,
            zone.districts,
            zone.wards,
            zone.postal_codes,
            zone.coverage_geojson,
        )
    ):
        db.rollback()
        raise HTTPException(
            422,
            "Zone must contain coverage or cover the entire country",
        )
    _commit(db)
    db.refresh(zone)
    return zone


@router.delete("/me/zones/{zone_id}")
def deactivate_my_company_zone(
    zone_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(
        membership, LogisticsCompanyPermission.zones_manage
    )
    zone = (
        db.query(ShippingZone)
        .filter(
            ShippingZone.id == zone_id,
            ShippingZone.logistics_company_id == membership.logistics_company_id,
        )
        .first()
    )
    if not zone:
        raise HTTPException(404, "Shipping zone not found")
    zone.is_active = False
    _commit(db)
    return {"message": "Shipping zone deactivated"}


    
# Rates
    
@router.get("/rates", response_model=PaginatedShippingRateResponse)
def list_rates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=150),
    company_id: UUID | None = Query(None),
    active: bool | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_rates_read.value)
    ),
):
    query = (
        db.query(ShippingRate)
        .join(ShippingMethod, ShippingRate.method_id == ShippingMethod.id)
        .join(ShippingZone, ShippingRate.zone_id == ShippingZone.id)
        .options(joinedload(ShippingRate.zone), joinedload(ShippingRate.method))
    )

    if company_id:
        query = query.filter(ShippingMethod.logistics_company_id == company_id)
    if active is not None:
        query = query.filter(ShippingRate.is_active.is_(active))

    term = (search or "").strip()
    if term:
        pattern = f"%{term}%"
        query = query.filter(
            or_(
                ShippingMethod.name.ilike(pattern),
                ShippingMethod.carrier_name.ilike(pattern),
                ShippingZone.name.ilike(pattern),
                ShippingZone.country.ilike(pattern),
                ShippingRate.currency.ilike(pattern),
            )
        )

    total = query.count()
    rows = (
        query.order_by(ShippingRate.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": _pages(total, page_size),
        "results": rows,
    }


@router.post("/rates", response_model=ShippingRateResponse, status_code=201)
def create_rate(
    data: ShippingRateCreate,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_rates_manage.value)
    ),
):
    zone = db.get(ShippingZone, data.zone_id)
    if not zone:
        raise HTTPException(404, "Shipping zone not found")
    method = db.get(ShippingMethod, data.method_id)
    if not method:
        raise HTTPException(404, "Logistics service not found")
    if zone.logistics_company_id not in (None, method.logistics_company_id):
        raise HTTPException(409, "Shipping zone and service belong to different companies")

    rate = ShippingRate(**data.model_dump())
    db.add(rate)
    _commit(db)

    return (
        db.query(ShippingRate)
        .options(joinedload(ShippingRate.zone), joinedload(ShippingRate.method))
        .filter(ShippingRate.id == rate.id)
        .one()
    )


@router.patch("/rates/{rate_id}", response_model=ShippingRateResponse)
def update_rate(
    rate_id: UUID,
    data: ShippingRateCreate,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_rates_manage.value)
    ),
):
    rate = db.get(ShippingRate, rate_id)
    if not rate:
        raise HTTPException(404, "Shipping rate not found")

    zone = db.get(ShippingZone, data.zone_id)
    if not zone:
        raise HTTPException(404, "Shipping zone not found")
    method = db.get(ShippingMethod, data.method_id)
    if not method:
        raise HTTPException(404, "Logistics service not found")
    if zone.logistics_company_id not in (None, method.logistics_company_id):
        raise HTTPException(409, "Shipping zone and service belong to different companies")

    for key, value in data.model_dump().items():
        setattr(rate, key, value)

    _commit(db)

    return (
        db.query(ShippingRate)
        .options(joinedload(ShippingRate.zone), joinedload(ShippingRate.method))
        .filter(ShippingRate.id == rate.id)
        .one()
    )


@router.delete("/rates/{rate_id}")
def deactivate_rate(
    rate_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_rates_manage.value)
    ),
):
    rate = db.get(ShippingRate, rate_id)
    if not rate:
        raise HTTPException(404, "Shipping rate not found")
    rate.is_active = False
    _commit(db)
    return {"message": "Shipping rate deactivated"}


def _company_zone(db: Session, company_id: UUID, zone_id: UUID) -> ShippingZone:
    zone = (
        db.query(ShippingZone)
        .filter(
            ShippingZone.id == zone_id,
            ShippingZone.logistics_company_id == company_id,
        )
        .first()
    )
    if not zone:
        raise HTTPException(404, "Company shipping zone not found")
    return zone


def _company_service(
    db: Session, company_id: UUID, service_id: UUID
) -> ShippingMethod:
    service = (
        db.query(ShippingMethod)
        .filter(
            ShippingMethod.id == service_id,
            ShippingMethod.logistics_company_id == company_id,
        )
        .first()
    )
    if not service:
        raise HTTPException(404, "Company logistics service not found")
    return service


@router.get("/me/pricing", response_model=LogisticsPricingSettingsResponse)
def my_pricing_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership or not membership.company:
        raise HTTPException(403, "User is not linked to a logistics company")
    return {
        "logistics_company_id": membership.logistics_company_id,
        "multi_seller_pricing_strategy": membership.company.multi_seller_pricing_strategy,
        "supported_strategies": [
            MultiSellerPricingStrategy.farthest_seller,
            MultiSellerPricingStrategy.sum_individual,
        ],
    }


@router.patch("/me/pricing", response_model=LogisticsPricingSettingsResponse)
def update_my_pricing_settings(
    data: LogisticsPricingSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership or not membership.company:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(
        membership, LogisticsCompanyPermission.rates_manage
    )
    supported = {
        MultiSellerPricingStrategy.farthest_seller,
        MultiSellerPricingStrategy.sum_individual,
    }
    if data.multi_seller_pricing_strategy not in supported:
        raise HTTPException(409, "Selected pricing strategy is not available for launch")
    membership.company.multi_seller_pricing_strategy = data.multi_seller_pricing_strategy
    _commit(db)
    return {
        "logistics_company_id": membership.logistics_company_id,
        "multi_seller_pricing_strategy": membership.company.multi_seller_pricing_strategy,
        "supported_strategies": sorted(supported, key=lambda item: item.value),
    }


@router.get("/me/services", response_model=PaginatedShippingMethodResponse)
def my_company_services(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    active: bool | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    query = db.query(ShippingMethod).filter(
        ShippingMethod.logistics_company_id == membership.logistics_company_id
    )
    if active is not None:
        query = query.filter(ShippingMethod.is_active.is_(active))
    total = query.count()
    rows = query.order_by(ShippingMethod.name).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "total_pages": _pages(total, page_size), "results": rows}


@router.post("/me/services", response_model=ShippingMethodResponse, status_code=201)
def create_my_company_service(
    data: ShippingMethodCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(membership, LogisticsCompanyPermission.rates_manage)
    if data.logistics_company_id not in (None, membership.logistics_company_id):
        raise HTTPException(403, "Cannot create a service for another company")
    values = data.model_dump(exclude={"logistics_company_id"})
    service = ShippingMethod(
        logistics_company_id=membership.logistics_company_id,
        carrier_name=data.carrier_name or membership.company.name,
        **{key: value for key, value in values.items() if key != "carrier_name"},
    )
    db.add(service); _commit(db); db.refresh(service); return service


@router.patch("/me/services/{service_id}", response_model=ShippingMethodResponse)
def update_my_company_service(
    service_id: UUID,
    data: ShippingMethodUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(membership, LogisticsCompanyPermission.rates_manage)
    service = _company_service(db, membership.logistics_company_id, service_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("logistics_company_id") not in (None, membership.logistics_company_id):
        raise HTTPException(403, "Cannot transfer a service to another company")
    changes.pop("logistics_company_id", None)
    for key, value in changes.items(): setattr(service, key, value)
    _commit(db); db.refresh(service); return service


@router.delete("/me/services/{service_id}")
def deactivate_my_company_service(
    service_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(membership, LogisticsCompanyPermission.rates_manage)
    service = _company_service(db, membership.logistics_company_id, service_id)
    service.is_active = False; _commit(db); return {"message": "Logistics service deactivated"}


@router.get("/me/rates", response_model=PaginatedShippingRateResponse)
def my_company_rates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    query = db.query(ShippingRate).join(ShippingMethod).options(joinedload(ShippingRate.zone), joinedload(ShippingRate.method)).filter(ShippingMethod.logistics_company_id == membership.logistics_company_id)
    total = query.count(); rows = query.order_by(ShippingRate.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "total_pages": _pages(total, page_size), "results": rows}


@router.post("/me/rates", response_model=ShippingRateResponse, status_code=201)
def create_my_company_rate(
    data: ShippingRateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(membership, LogisticsCompanyPermission.rates_manage)
    _company_zone(db, membership.logistics_company_id, data.zone_id)
    _company_service(db, membership.logistics_company_id, data.method_id)
    rate = ShippingRate(**data.model_dump()); db.add(rate); _commit(db)
    return db.query(ShippingRate).options(joinedload(ShippingRate.zone), joinedload(ShippingRate.method)).filter(ShippingRate.id == rate.id).one()


@router.patch("/me/rates/{rate_id}", response_model=ShippingRateResponse)
def update_my_company_rate(
    rate_id: UUID,
    data: ShippingRateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(membership, LogisticsCompanyPermission.rates_manage)
    _company_zone(db, membership.logistics_company_id, data.zone_id)
    _company_service(db, membership.logistics_company_id, data.method_id)
    rate = db.query(ShippingRate).join(ShippingMethod).filter(ShippingRate.id == rate_id, ShippingMethod.logistics_company_id == membership.logistics_company_id).first()
    if not rate: raise HTTPException(404, "Company shipping rate not found")
    for key, value in data.model_dump().items(): setattr(rate, key, value)
    _commit(db)
    return db.query(ShippingRate).options(joinedload(ShippingRate.zone), joinedload(ShippingRate.method)).filter(ShippingRate.id == rate.id).one()


@router.delete("/me/rates/{rate_id}")
def deactivate_my_company_rate(
    rate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(membership, LogisticsCompanyPermission.rates_manage)
    rate = db.query(ShippingRate).join(ShippingMethod).filter(ShippingRate.id == rate_id, ShippingMethod.logistics_company_id == membership.logistics_company_id).first()
    if not rate: raise HTTPException(404, "Company shipping rate not found")
    rate.is_active = False; _commit(db); return {"message": "Shipping rate deactivated"}


    
# API / webhook integration metadata.
# Secrets are referenced from environment/secret manager; they are not stored
# as clear text in this table.
    
@router.get(
    "/companies/{company_id}/integration",
    response_model=LogisticsIntegrationResponse,
)
def get_integration(
    company_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_integrations_read.value)
    ),
):
    integration = (
        db.query(LogisticsIntegrationConfig)
        .filter(LogisticsIntegrationConfig.logistics_company_id == company_id)
        .first()
    )
    if not integration:
        raise HTTPException(404, "Logistics integration configuration not found")
    return integration


@router.put(
    "/companies/{company_id}/integration",
    response_model=LogisticsIntegrationResponse,
)
def upsert_integration(
    company_id: UUID,
    data: LogisticsIntegrationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_integrations_manage.value)
    ),
):
    company = db.get(LogisticsCompany, company_id)
    if not company:
        raise HTTPException(404, "Logistics company not found")

    integration = (
        db.query(LogisticsIntegrationConfig)
        .filter(LogisticsIntegrationConfig.logistics_company_id == company_id)
        .first()
    )
    if integration is None:
        integration = LogisticsIntegrationConfig(
            logistics_company_id=company_id,
            **data.model_dump(),
        )
        db.add(integration)
    else:
        for key, value in data.model_dump().items():
            setattr(integration, key, value)

    company.supports_webhooks = bool(data.outbound_webhook_url)
    _commit(db)
    db.refresh(integration)
    return integration


@router.patch(
    "/companies/{company_id}/integration",
    response_model=LogisticsIntegrationResponse,
)
def update_integration(
    company_id: UUID,
    data: LogisticsIntegrationUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.logistics_integrations_manage.value)
    ),
):
    integration = (
        db.query(LogisticsIntegrationConfig)
        .filter(LogisticsIntegrationConfig.logistics_company_id == company_id)
        .first()
    )
    if not integration:
        raise HTTPException(404, "Logistics integration configuration not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(integration, key, value)

    _commit(db)
    db.refresh(integration)
    return integration


@router.get("/me/integration", response_model=LogisticsIntegrationResponse)
def my_integration(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    integration = db.query(LogisticsIntegrationConfig).filter(
        LogisticsIntegrationConfig.logistics_company_id == membership.logistics_company_id
    ).first()
    if not integration:
        raise HTTPException(404, "Logistics integration configuration not found")
    return integration


@router.put("/me/integration", response_model=LogisticsIntegrationResponse)
def upsert_my_integration(
    data: LogisticsIntegrationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(membership, LogisticsCompanyPermission.integrations_manage)
    integration = db.query(LogisticsIntegrationConfig).filter(
        LogisticsIntegrationConfig.logistics_company_id == membership.logistics_company_id
    ).first()
    if integration is None:
        integration = LogisticsIntegrationConfig(
            logistics_company_id=membership.logistics_company_id,
            **data.model_dump(),
        )
        db.add(integration)
    else:
        for key, value in data.model_dump().items(): setattr(integration, key, value)
    membership.company.supports_webhooks = bool(data.outbound_webhook_url)
    _commit(db); db.refresh(integration); return integration


@router.get(
    "/me/webhook-events", response_model=PaginatedLogisticsWebhookEventResponse
)
def my_webhook_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    direction: str | None = Query(None, pattern="^(inbound|outbound)$"),
    processed: bool | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    query = db.query(LogisticsWebhookEvent).filter(
        LogisticsWebhookEvent.logistics_company_id == membership.logistics_company_id
    )
    if direction: query = query.filter(LogisticsWebhookEvent.direction == direction)
    if processed is not None: query = query.filter(LogisticsWebhookEvent.processed.is_(processed))
    total = query.count()
    rows = query.order_by(LogisticsWebhookEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "total_pages": _pages(total, page_size), "results": rows}


@router.get("/me/dashboard", response_model=LogisticsDashboardResponse)
def my_logistics_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    company_id = membership.logistics_company_id
    shipment_rows = db.query(Shipment.status, func.count(Shipment.id)).filter(
        Shipment.logistics_company_id == company_id
    ).group_by(Shipment.status).all()
    pickup_rows = db.query(LogisticsPickupJob.status, func.count(LogisticsPickupJob.id)).filter(
        LogisticsPickupJob.logistics_company_id == company_id
    ).group_by(LogisticsPickupJob.status).all()
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    event_query = db.query(LogisticsWebhookEvent).filter(
        LogisticsWebhookEvent.logistics_company_id == company_id,
        LogisticsWebhookEvent.created_at >= since,
    )
    integration = db.query(LogisticsIntegrationConfig).filter(
        LogisticsIntegrationConfig.logistics_company_id == company_id
    ).first()
    shipments = {getattr(status_value, "value", str(status_value)): count for status_value, count in shipment_rows}
    pickups = {getattr(status_value, "value", str(status_value)): count for status_value, count in pickup_rows}
    return {
        "logistics_company_id": company_id,
        "members": db.query(LogisticsCompanyUser).filter(LogisticsCompanyUser.logistics_company_id == company_id, LogisticsCompanyUser.is_active.is_(True)).count(),
        "active_zones": db.query(ShippingZone).filter(ShippingZone.logistics_company_id == company_id, ShippingZone.is_active.is_(True)).count(),
        "active_services": db.query(ShippingMethod).filter(ShippingMethod.logistics_company_id == company_id, ShippingMethod.is_active.is_(True)).count(),
        "active_rates": db.query(ShippingRate).join(ShippingMethod).filter(ShippingMethod.logistics_company_id == company_id, ShippingRate.is_active.is_(True)).count(),
        "shipments_total": sum(shipments.values()), "shipments_by_status": shipments,
        "pickup_jobs_total": sum(pickups.values()), "pickup_jobs_by_status": pickups,
        "webhook_events_24h": event_query.count(),
        "webhook_failures_24h": event_query.filter(or_(LogisticsWebhookEvent.error_message.isnot(None), LogisticsWebhookEvent.http_status >= 400)).count(),
        "integration_configured": integration is not None,
        "integration_active": bool(integration and integration.is_active),
    }


    
# Logistics-company operational workspace.
# A normal RBAC user is linked to a logistics company and can only see that
# company's shipments, regardless of the role name assigned to the account.
    
@router.get("/me/company", response_model=LogisticsCompanyResponse)
def my_logistics_company(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership or not membership.company:
        raise HTTPException(403, "User is not linked to a logistics company")
    return membership.company


@router.get("/me/account", response_model=LogisticsCompanyAccountResponse)
def my_logistics_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership or not membership.company:
        raise HTTPException(403, "User is not linked to a logistics company")

    permissions = get_user_permissions(db, current_user)
    return {
        "company": membership.company,
        "membership_id": membership.id,
        "title": membership.title,
        "member_role": membership.member_role,
        "effective_permissions": sorted(
            _effective_company_permissions(membership), key=lambda item: item.value
        ),
        "is_primary_contact": membership.is_primary_contact,
        "can_manage_profile": (
            membership.is_primary_contact
            or PermissionCode.logistics_profile_manage.value in permissions
            or LogisticsCompanyPermission.profile_manage
            in _effective_company_permissions(membership)
        ),
    }


LOGISTICS_DOCUMENT_UPLOAD_DIR = Path("private_uploads/logistics_documents")
LOGISTICS_DOCUMENT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_LOGISTICS_DOCUMENT_SIZE = 15 * 1024 * 1024
ALLOWED_LOGISTICS_DOCUMENT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
REQUIRED_LOGISTICS_DOCUMENT_TYPES = {
    LogisticsDocumentType.tin_certificate.value,
    LogisticsDocumentType.registration_certificate.value,
    LogisticsDocumentType.business_license.value,
    LogisticsDocumentType.representative_id.value,
}
OPTIONAL_LOGISTICS_DOCUMENT_TYPES = {
    LogisticsDocumentType.proof_of_address.value,
    LogisticsDocumentType.insurance_certificate.value,
    LogisticsDocumentType.logistics_license.value,
    LogisticsDocumentType.other.value,
}


def _current_company_documents(db: Session, company_id: UUID) -> list[LogisticsCompanyDocument]:
    return (
        db.query(LogisticsCompanyDocument)
        .filter(
            LogisticsCompanyDocument.logistics_company_id == company_id,
            LogisticsCompanyDocument.is_current.is_(True),
            LogisticsCompanyDocument.deleted_at.is_(None),
        )
        .order_by(LogisticsCompanyDocument.document_type.asc())
        .all()
    )


def _document_requirements(db: Session, company: LogisticsCompany) -> dict:
    documents = _current_company_documents(db, company.id)
    by_type = {row.document_type: row for row in documents}
    uploaded = sorted(REQUIRED_LOGISTICS_DOCUMENT_TYPES.intersection(by_type))
    missing = sorted(REQUIRED_LOGISTICS_DOCUMENT_TYPES.difference(by_type))
    all_approved = not missing and all(
        by_type[item].status == LogisticsDocumentStatus.approved.value
        for item in REQUIRED_LOGISTICS_DOCUMENT_TYPES
    )
    state = ((company.metadata_json or {}).get("onboarding") or {}).get("state")
    return {
        "required_types": sorted(REQUIRED_LOGISTICS_DOCUMENT_TYPES),
        "optional_types": sorted(OPTIONAL_LOGISTICS_DOCUMENT_TYPES),
        "uploaded_required_types": uploaded,
        "missing_required_types": missing,
        "all_required_uploaded": not missing,
        "all_required_approved": all_approved,
        "editing_locked": state in {"under_review", "approved"},
    }


def _ensure_company_documents_editable(company: LogisticsCompany) -> None:
    state = ((company.metadata_json or {}).get("onboarding") or {}).get("state")
    if company.status == LogisticsCompanyStatus.active or state in {"under_review", "approved"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Company documents are view-only while administrator review is in progress "
                "or after approval. They become editable again when changes are requested."
            ),
        )


def _document_response(row: LogisticsCompanyDocument, *, can_edit: bool = False) -> dict:
    return {
        "id": row.id,
        "logistics_company_id": row.logistics_company_id,
        "document_type": row.document_type,
        "document_name": row.document_name,
        "original_filename": row.original_filename,
        "mime_type": row.mime_type,
        "file_size": row.file_size,
        "version": row.version,
        "is_current": row.is_current,
        "status": row.status,
        "review_comment": row.review_comment,
        "uploaded_by_user_id": row.uploaded_by_user_id,
        "reviewed_by_user_id": row.reviewed_by_user_id,
        "reviewed_at": row.reviewed_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "can_edit": can_edit,
        "can_delete": can_edit,
    }


def _get_company_document(db: Session, company_id: UUID, document_id: UUID, *, current_only: bool = True) -> LogisticsCompanyDocument:
    query = db.query(LogisticsCompanyDocument).filter(
        LogisticsCompanyDocument.id == document_id,
        LogisticsCompanyDocument.logistics_company_id == company_id,
        LogisticsCompanyDocument.deleted_at.is_(None),
    )
    if current_only:
        query = query.filter(LogisticsCompanyDocument.is_current.is_(True))
    row = query.first()
    if not row:
        raise HTTPException(404, "Logistics company document not found")
    return row


def _resolve_logistics_document_file(row: LogisticsCompanyDocument) -> Path:
    path = Path(row.document_url).resolve()
    root = LOGISTICS_DOCUMENT_UPLOAD_DIR.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(404, "Document file is unavailable") from exc
    if not path.is_file():
        raise HTTPException(404, "Document file is unavailable")
    return path


async def _save_logistics_document(company_id: UUID, document_type: str, upload: UploadFile) -> tuple[str, str, str, int]:
    if not upload.filename:
        raise HTTPException(400, "Uploaded document must have a filename")
    extension = Path(upload.filename).suffix.lower()
    if extension not in ALLOWED_LOGISTICS_DOCUMENT_EXTENSIONS:
        raise HTTPException(400, "Only PDF, PNG, JPG and JPEG documents are allowed")
    content = await upload.read()
    if not content:
        raise HTTPException(400, "Uploaded document is empty")
    if len(content) > MAX_LOGISTICS_DOCUMENT_SIZE:
        raise HTTPException(413, "Company document must not exceed 15 MB")
    media_type = upload.content_type or mimetypes.guess_type(upload.filename)[0] or "application/octet-stream"
    filename = f"{company_id}_{document_type}_{uuid4().hex}{extension}"
    path = LOGISTICS_DOCUMENT_UPLOAD_DIR / filename
    path.write_bytes(content)
    return str(path), upload.filename, media_type, len(content)


def _remove_logistics_document_file(path_value: str | None) -> None:
    if not path_value:
        return
    try:
        path = Path(path_value).resolve()
        path.relative_to(LOGISTICS_DOCUMENT_UPLOAD_DIR.resolve())
        if path.is_file():
            path.unlink()
    except (OSError, ValueError):
        pass


def _set_onboarding_state(company: LogisticsCompany, state_value: str, **values) -> None:
    metadata = dict(company.metadata_json or {})
    onboarding = dict(metadata.get("onboarding") or {})
    onboarding.update({"state": state_value, **values})
    metadata["onboarding"] = onboarding
    company.metadata_json = metadata


@router.get("/me/documents/requirements", response_model=LogisticsDocumentRequirementsResponse)
def my_logistics_document_requirements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership or not membership.company:
        raise HTTPException(403, "User is not linked to a logistics company")
    return _document_requirements(db, membership.company)


@router.get("/me/documents", response_model=PaginatedLogisticsDocumentResponse)
def list_my_logistics_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    include_history: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership or not membership.company:
        raise HTTPException(403, "User is not linked to a logistics company")
    query = db.query(LogisticsCompanyDocument).filter(
        LogisticsCompanyDocument.logistics_company_id == membership.company.id,
        LogisticsCompanyDocument.deleted_at.is_(None),
    )
    if not include_history:
        query = query.filter(LogisticsCompanyDocument.is_current.is_(True))
    total = query.count()
    rows = query.order_by(LogisticsCompanyDocument.document_type.asc(), LogisticsCompanyDocument.version.desc()).offset((page - 1) * page_size).limit(page_size).all()
    can_edit = not _document_requirements(db, membership.company)["editing_locked"]
    return {"total": total, "page": page, "page_size": page_size, "total_pages": _pages(total, page_size), "results": [_document_response(row, can_edit=can_edit and row.is_current) for row in rows]}


@router.post("/me/documents", response_model=LogisticsDocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_my_logistics_document(
    document_type: LogisticsDocumentType = Form(...),
    document_name: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership or not membership.company:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(membership, LogisticsCompanyPermission.profile_manage)
    company = membership.company
    _ensure_company_documents_editable(company)
    existing = db.query(LogisticsCompanyDocument).filter(
        LogisticsCompanyDocument.logistics_company_id == company.id,
        LogisticsCompanyDocument.document_type == document_type.value,
        LogisticsCompanyDocument.is_current.is_(True),
        LogisticsCompanyDocument.deleted_at.is_(None),
    ).first()
    if existing:
        raise HTTPException(409, f"A current {document_type.value} document already exists; update it instead")
    path, original, mime, size = await _save_logistics_document(company.id, document_type.value, file)
    row = LogisticsCompanyDocument(
        logistics_company_id=company.id, document_type=document_type.value,
        document_name=(document_name or document_type.value.replace("_", " ").title()).strip(),
        document_url=path, original_filename=original, mime_type=mime, file_size=size,
        version=1, is_current=True, status=LogisticsDocumentStatus.pending_review.value,
        uploaded_by_user_id=current_user.id,
    )
    try:
        db.add(row); _commit(db); db.refresh(row)
    except Exception:
        _remove_logistics_document_file(path); raise
    return _document_response(row, can_edit=True)


@router.get("/me/documents/{document_id}", response_model=LogisticsDocumentResponse)
def get_my_logistics_document(document_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    membership = _membership_for_user(db, current_user.id)
    if not membership or not membership.company:
        raise HTTPException(403, "User is not linked to a logistics company")
    row = _get_company_document(db, membership.company.id, document_id, current_only=False)
    can_edit = row.is_current and not _document_requirements(db, membership.company)["editing_locked"]
    return _document_response(row, can_edit=can_edit)


@router.get("/me/documents/{document_id}/view")
def view_my_logistics_document(document_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    membership = _membership_for_user(db, current_user.id)
    if not membership or not membership.company:
        raise HTTPException(403, "User is not linked to a logistics company")
    row = _get_company_document(db, membership.company.id, document_id, current_only=False)
    path = _resolve_logistics_document_file(row)
    return FileResponse(path=path, media_type=row.mime_type, filename=row.original_filename, content_disposition_type="inline")


@router.put("/me/documents/{document_id}", response_model=LogisticsDocumentResponse)
async def update_my_logistics_document(
    document_id: UUID, document_name: str | None = Form(default=None), file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership or not membership.company:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(membership, LogisticsCompanyPermission.profile_manage)
    company = membership.company; _ensure_company_documents_editable(company)
    current = _get_company_document(db, company.id, document_id)
    if current.status in {LogisticsDocumentStatus.under_review.value, LogisticsDocumentStatus.approved.value}:
        raise HTTPException(409, "This document is view-only until an administrator requests changes")
    if document_name is None and file is None:
        raise HTTPException(400, "Provide document_name, file, or both")
    if file is None:
        current.document_name = (document_name or current.document_name).strip(); _commit(db); db.refresh(current)
        return _document_response(current, can_edit=True)
    path, original, mime, size = await _save_logistics_document(company.id, current.document_type, file)
    next_version = current.version + 1
    current.is_current = False
    row = LogisticsCompanyDocument(
        logistics_company_id=company.id, document_type=current.document_type,
        document_name=(document_name or current.document_name).strip(), document_url=path,
        original_filename=original, mime_type=mime, file_size=size, version=next_version, is_current=True,
        status=LogisticsDocumentStatus.pending_review.value, uploaded_by_user_id=current_user.id,
    )
    try:
        db.add(row); _commit(db); db.refresh(row)
    except Exception:
        _remove_logistics_document_file(path); raise
    return _document_response(row, can_edit=True)


@router.delete("/me/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_logistics_document(document_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    membership = _membership_for_user(db, current_user.id)
    if not membership or not membership.company:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(membership, LogisticsCompanyPermission.profile_manage)
    company = membership.company; _ensure_company_documents_editable(company)
    row = _get_company_document(db, company.id, document_id)
    if row.status in {LogisticsDocumentStatus.under_review.value, LogisticsDocumentStatus.approved.value}:
        raise HTTPException(409, "This document is view-only until an administrator requests changes")
    row.is_current = False; row.deleted_at = datetime.now(timezone.utc); _commit(db)
    return None


@router.get("/companies/{company_id}/documents", response_model=PaginatedLogisticsDocumentResponse)
def admin_list_logistics_documents(
    company_id: UUID, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), include_history: bool = Query(False),
    db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.logistics_documents_read.value)),
):
    company = db.get(LogisticsCompany, company_id)
    if not company: raise HTTPException(404, "Logistics company not found")
    query = db.query(LogisticsCompanyDocument).filter(LogisticsCompanyDocument.logistics_company_id == company_id, LogisticsCompanyDocument.deleted_at.is_(None))
    if not include_history: query = query.filter(LogisticsCompanyDocument.is_current.is_(True))
    total=query.count(); rows=query.order_by(LogisticsCompanyDocument.document_type.asc(), LogisticsCompanyDocument.version.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total":total,"page":page,"page_size":page_size,"total_pages":_pages(total,page_size),"results":[_document_response(row) for row in rows]}


@router.get("/companies/{company_id}/documents/{document_id}/view")
def admin_view_logistics_document(
    company_id: UUID, document_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.logistics_documents_read.value)),
):
    row=_get_company_document(db, company_id, document_id, current_only=False); path=_resolve_logistics_document_file(row)
    return FileResponse(path=path, media_type=row.mime_type, filename=row.original_filename, content_disposition_type="inline")


@router.post("/companies/{company_id}/documents/review/start", response_model=LogisticsOnboardingStatusResponse)
def start_logistics_document_review(
    company_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.logistics_documents_review.value)),
):
    company=db.get(LogisticsCompany, company_id)
    if not company: raise HTTPException(404, "Logistics company not found")
    readiness=_company_onboarding_status(db, company)
    if not readiness["ready_for_review"]: raise HTTPException(409, "Company onboarding is not ready for review")
    for row in _current_company_documents(db, company_id):
        if row.status == LogisticsDocumentStatus.pending_review.value:
            row.status = LogisticsDocumentStatus.under_review.value
    _set_onboarding_state(company, "under_review", review_started_at=datetime.now(timezone.utc).isoformat(), review_started_by_user_id=str(current_user.id))
    _commit(db); db.refresh(company)
    return _company_onboarding_status(db, company)


@router.post("/companies/{company_id}/documents/{document_id}/review", response_model=LogisticsDocumentResponse)
def review_logistics_document(
    company_id: UUID, document_id: UUID, data: LogisticsDocumentReviewRequest,
    db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.logistics_documents_review.value)),
):
    company=db.get(LogisticsCompany, company_id)
    if not company: raise HTTPException(404, "Logistics company not found")
    row=_get_company_document(db, company_id, document_id)
    if row.status not in {LogisticsDocumentStatus.pending_review.value, LogisticsDocumentStatus.under_review.value, LogisticsDocumentStatus.changes_requested.value, LogisticsDocumentStatus.rejected.value}:
        if row.status == LogisticsDocumentStatus.approved.value and data.decision == "approve": return _document_response(row)
        raise HTTPException(409, "Document is not in a reviewable state")
    row.status = {"approve": LogisticsDocumentStatus.approved.value, "changes_requested": LogisticsDocumentStatus.changes_requested.value, "rejected": LogisticsDocumentStatus.rejected.value}[data.decision]
    row.review_comment=(data.comment or "").strip() or None; row.reviewed_by_user_id=current_user.id; row.reviewed_at=datetime.now(timezone.utc)
    if data.decision in {"changes_requested", "rejected"}:
        _set_onboarding_state(company, "changes_requested" if data.decision == "changes_requested" else "rejected", reviewed_at=datetime.now(timezone.utc).isoformat(), reviewed_by_user_id=str(current_user.id), review_note=row.review_comment)
        company.status = LogisticsCompanyStatus.pending
    _commit(db); db.refresh(row)
    return _document_response(row)


def _company_onboarding_status(db: Session, company: LogisticsCompany) -> dict:
    """Build one authoritative readiness view for company and admin workflows."""
    company_id = company.id
    required_profile_values = (
        company.legal_name,
        company.registration_number,
        company.tax_identification_number,
        company.contact_name,
        company.contact_email,
        company.contact_phone,
        company.address_line1,
        company.city,
        company.region,
    )
    profile_complete = all(
        isinstance(value, str) and bool(value.strip()) for value in required_profile_values
    )
    has_zones = db.query(ShippingZone.id).filter(
        ShippingZone.logistics_company_id == company_id,
        ShippingZone.is_active.is_(True),
    ).first() is not None
    has_services = db.query(ShippingMethod.id).filter(
        ShippingMethod.logistics_company_id == company_id,
        ShippingMethod.is_active.is_(True),
    ).first() is not None
    has_rates = db.query(ShippingRate.id).join(
        ShippingMethod, ShippingRate.method_id == ShippingMethod.id
    ).filter(
        ShippingMethod.logistics_company_id == company_id,
        ShippingMethod.is_active.is_(True),
        ShippingRate.is_active.is_(True),
    ).first() is not None
    has_payout_account = db.query(LogisticsPayoutAccount.id).filter(
        LogisticsPayoutAccount.logistics_company_id == company_id,
        LogisticsPayoutAccount.is_active.is_(True),
    ).first() is not None
    integration = db.query(LogisticsIntegrationConfig).filter(
        LogisticsIntegrationConfig.logistics_company_id == company_id
    ).first()
    has_webhook = bool(
        integration
        and integration.is_active
        and (integration.outbound_webhook_url or integration.api_base_url)
    )
    document_requirements = _document_requirements(db, company)

    steps = [
        {"key": "company_profile", "label": "Company profile", "description": "Add legal, tax, contact and operating-address details.", "completed": profile_complete, "required": True, "href": "/logistics/settings"},
        {"key": "company_documents", "label": "Company documents", "description": "Upload TIN, registration, business licence and authorized representative ID.", "completed": document_requirements["all_required_uploaded"], "required": True, "href": "/logistics/settings?section=documents"},
        {"key": "zones", "label": "Delivery zones", "description": "Define at least one active delivery coverage zone.", "completed": has_zones, "required": True, "href": "/logistics/pricing"},
        {"key": "services", "label": "Delivery services", "description": "Create at least one active delivery service and its ETA.", "completed": has_services, "required": True, "href": "/logistics/pricing"},
        {"key": "rates", "label": "Shipping charges", "description": "Configure at least one active rate for your service and zone.", "completed": has_rates, "required": True, "href": "/logistics/pricing"},
        {"key": "payout_account", "label": "Payment account", "description": "Add the account where Xerin should send your settlements.", "completed": has_payout_account, "required": True, "href": "/logistics/wallet"},
        {"key": "webhook", "label": "Webhook integration", "description": "Connect your own system now, or skip this optional step.", "completed": has_webhook, "required": False, "href": "/logistics/integration"},
    ]
    required_steps = [step for step in steps if step["required"]]
    completed = sum(bool(step["completed"]) for step in required_steps)
    ready = completed == len(required_steps)
    next_step = next((step for step in required_steps if not step["completed"]), None)
    onboarding = (company.metadata_json or {}).get("onboarding") or {}
    stored_state = onboarding.get("state")
    if company.status == LogisticsCompanyStatus.active:
        state = "approved"
    elif stored_state == "under_review":
        state = "under_review"
    elif stored_state == "submitted" and ready:
        state = "submitted"
    elif stored_state == "changes_requested":
        state = "changes_requested"
    elif stored_state == "rejected":
        state = "rejected"
    elif ready:
        # Completing every required item automatically places the company in
        # the admin-decision state; a separate submit click is not required.
        state = "submitted"
    elif completed:
        state = "in_progress"
    else:
        state = "invited"
    return {
        "company_id": company_id,
        "company_name": company.name,
        "company_status": company.status,
        "state": state,
        "required_completed": completed,
        "required_total": len(required_steps),
        "progress_percent": round((completed / len(required_steps)) * 100),
        "ready_for_review": ready,
        "steps": steps,
        "next_step": next_step,
        "submitted_at": onboarding.get("submitted_at"),
        "reviewed_at": onboarding.get("reviewed_at"),
        "review_note": onboarding.get("review_note"),
    }


@router.get("/me/onboarding", response_model=LogisticsOnboardingStatusResponse)
def my_logistics_onboarding(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership or not membership.company:
        raise HTTPException(403, "User is not linked to a logistics company")
    return _company_onboarding_status(db, membership.company)


@router.get("/onboarding/review-queue", response_model=PaginatedLogisticsOnboardingResponse)
def logistics_onboarding_review_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=150),
    state_filter: str | None = Query(None, alias="state"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.logistics_companies_read.value)),
):
    """Admin queue for company onboarding readiness and approval decisions."""
    allowed_states = {"invited", "in_progress", "ready_for_review", "submitted", "under_review", "changes_requested", "rejected", "approved"}
    if state_filter and state_filter not in allowed_states:
        raise HTTPException(422, "Invalid onboarding state filter")
    query = db.query(LogisticsCompany)
    term = (search or "").strip()
    if term:
        pattern = f"%{term}%"
        query = query.filter(or_(
            LogisticsCompany.name.ilike(pattern),
            LogisticsCompany.code.ilike(pattern),
            LogisticsCompany.contact_email.ilike(pattern),
            LogisticsCompany.contact_phone.ilike(pattern),
        ))
    statuses = [_company_onboarding_status(db, company) for company in query.order_by(LogisticsCompany.created_at.desc()).all()]
    if state_filter:
        statuses = [item for item in statuses if item["state"] == state_filter]
    priority = {"under_review": 0, "submitted": 1, "changes_requested": 2, "rejected": 3, "ready_for_review": 4, "in_progress": 5, "invited": 6, "approved": 7}
    statuses.sort(key=lambda item: (priority.get(item["state"], 99), item["company_name"].lower()))
    total = len(statuses)
    start = (page - 1) * page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": _pages(total, page_size),
        "results": statuses[start:start + page_size],
    }


@router.post("/me/onboarding/submit", response_model=LogisticsOnboardingStatusResponse)
def submit_my_logistics_onboarding(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership or not membership.company:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(membership, LogisticsCompanyPermission.profile_manage)
    company = membership.company
    readiness = _company_onboarding_status(db, company)
    if company.status == LogisticsCompanyStatus.active:
        return readiness
    if not readiness["ready_for_review"]:
        missing = [step["label"] for step in readiness["steps"] if step["required"] and not step["completed"]]
        raise HTTPException(409, f"Complete required onboarding steps first: {', '.join(missing)}")
    metadata = dict(company.metadata_json or {})
    metadata["onboarding"] = {
        **(metadata.get("onboarding") or {}),
        "state": "submitted",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "submitted_by_user_id": str(current_user.id),
        "review_note": None,
    }
    company.metadata_json = metadata
    _commit(db)
    db.refresh(company)
    return _company_onboarding_status(db, company)


@router.get("/companies/{company_id}/onboarding", response_model=LogisticsOnboardingStatusResponse)
def review_company_onboarding_details(
    company_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.logistics_companies_read.value)),
):
    company = db.get(LogisticsCompany, company_id)
    if not company:
        raise HTTPException(404, "Logistics company not found")
    return _company_onboarding_status(db, company)


@router.post("/companies/{company_id}/onboarding/review", response_model=LogisticsOnboardingStatusResponse)
def review_company_onboarding(
    company_id: UUID,
    data: LogisticsOnboardingReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.logistics_companies_manage.value)),
):
    company = db.get(LogisticsCompany, company_id)
    if not company:
        raise HTTPException(404, "Logistics company not found")
    readiness = _company_onboarding_status(db, company)
    if data.decision == "approve" and not readiness["ready_for_review"]:
        raise HTTPException(409, "Company onboarding is incomplete and cannot be approved")
    document_requirements = _document_requirements(db, company)
    if data.decision == "approve" and not document_requirements["all_required_approved"]:
        raise HTTPException(409, "All required company documents must be approved before company approval")
    onboarding = (company.metadata_json or {}).get("onboarding") or {}

    now = datetime.now(timezone.utc).isoformat()
    metadata = dict(company.metadata_json or {})
    metadata["onboarding"] = {
        **onboarding,
        "state": "approved" if data.decision == "approve" else data.decision,
        "reviewed_at": now,
        "reviewed_by_user_id": str(current_user.id),
        "review_note": (data.note or "").strip() or None,
    }
    company.metadata_json = metadata
    company.status = LogisticsCompanyStatus.active if data.decision == "approve" else LogisticsCompanyStatus.pending
    _commit(db)
    db.refresh(company)

    recipient = company.contact_email
    if recipient:
        try:
            approved = data.decision == "approve"
            rejected = data.decision == "rejected"
            outcome = "approved" if approved else ("rejected" if rejected else "needs changes")
            detail = (
                "Your logistics company onboarding has been approved. You can now use the operational workspace."
                if approved
                else (
                    f"Your logistics company onboarding was not approved.\n\nReason: {(data.note or '').strip()}"
                    if rejected
                    else f"Your onboarding needs changes before approval.\n\nReview note: {(data.note or '').strip()}"
                )
            )
            send_email(
                to=recipient,
                subject=f"Xerin Logistics onboarding {outcome} – {company.name}",
                body=f"Hello {company.contact_name or company.name},\n\n{detail}\n\nSign in to Xerin Logistics to review the decision.",
            )
        except Exception:
            pass
    return _company_onboarding_status(db, company)


@router.patch("/me/company", response_model=LogisticsCompanyResponse)
def update_my_logistics_company(
    data: LogisticsCompanyProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership or not membership.company:
        raise HTTPException(403, "User is not linked to a logistics company")

    permissions = get_user_permissions(db, current_user)
    if (
        not membership.is_primary_contact
        and PermissionCode.logistics_profile_manage.value not in permissions
        and LogisticsCompanyPermission.profile_manage
        not in _effective_company_permissions(membership)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. Required: logistics_profile:manage",
        )

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(membership.company, key, value)

    _commit(db)
    db.refresh(membership.company)
    return membership.company


@router.get("/me/shipments", response_model=PaginatedShipmentResponse)
def my_company_shipments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=150),
    status_filter: ShipmentStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.logistics_shipments_read.value)
    ),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")

    query = (
        db.query(Shipment)
        .options(
            selectinload(Shipment.items),
            selectinload(Shipment.tracking_events),
            joinedload(Shipment.order),
        )
        .filter(Shipment.logistics_company_id == membership.logistics_company_id)
    )

    if status_filter:
        query = query.filter(Shipment.status == status_filter)

    term = (search or "").strip()
    if term:
        pattern = f"%{term}%"
        query = query.filter(
            or_(
                Shipment.tracking_number.ilike(pattern),
                Shipment.carrier_name.ilike(pattern),
            )
        )

    total = query.count()
    rows = (
        query.order_by(Shipment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": _pages(total, page_size),
        "results": rows,
    }


ALLOWED_LOGISTICS_TRANSITIONS = {
    ShipmentStatus.ready_for_dispatch: {ShipmentStatus.dispatched, ShipmentStatus.cancelled},
    ShipmentStatus.dispatched: {ShipmentStatus.in_transit, ShipmentStatus.delivery_failed},
    ShipmentStatus.in_transit: {
        ShipmentStatus.out_for_delivery,
        ShipmentStatus.delivery_failed,
        ShipmentStatus.returned_to_sender,
    },
    ShipmentStatus.out_for_delivery: {
        ShipmentStatus.delivery_failed,
        ShipmentStatus.returned_to_sender,
    },
    ShipmentStatus.delivery_failed: {
        ShipmentStatus.out_for_delivery,
        ShipmentStatus.returned_to_sender,
    },
}



@router.get(
    "/me/shipments/{shipment_id}/handover",
    response_model=ShipmentHandoverResponse,
)
def get_company_shipment_handover(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.logistics_shipments_read.value)
    ),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")

    handover = (
        db.query(ShipmentHandover)
        .filter(
            ShipmentHandover.shipment_id == shipment_id,
            ShipmentHandover.logistics_company_id == membership.logistics_company_id,
        )
        .first()
    )
    if not handover:
        raise HTTPException(404, "Handover record not found for this logistics company")
    return handover


@router.post(
    "/me/shipments/{shipment_id}/arrived-for-pickup",
    response_model=ShipmentHandoverResponse,
)
def confirm_courier_arrival_for_pickup(
    shipment_id: UUID,
    data: LogisticsCourierArrivalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.logistics_shipments_update.value)
    ),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")

    shipment = (
        db.query(Shipment)
        .filter(
            Shipment.id == shipment_id,
            Shipment.logistics_company_id == membership.logistics_company_id,
        )
        .with_for_update()
        .first()
    )
    if not shipment:
        raise HTTPException(404, "Shipment not found for this logistics company")
    if shipment.status != ShipmentStatus.ready_for_dispatch:
        raise HTTPException(
            409,
            "Courier arrival can only be confirmed for a shipment ready for dispatch",
        )

    seller_order = (
        db.query(SellerOrder)
        .filter(
            SellerOrder.order_id == shipment.order_id,
            SellerOrder.seller_id == shipment.seller_id,
        )
        .first()
    )
    if seller_order is None:
        raise HTTPException(409, "Seller order is missing for this shipment")

    handover = (
        db.query(ShipmentHandover)
        .filter(ShipmentHandover.shipment_id == shipment.id)
        .with_for_update()
        .first()
    )
    if handover is None:
        handover = ensure_shipment_handover(
            db, seller_order=seller_order, shipment=shipment
        )

    if handover.status == "seller_confirmed":
        return handover
    if handover.courier_arrived_at is not None:
        return handover

    now = datetime.now(timezone.utc)
    handover.status = "courier_arrived"
    handover.courier_arrived_at = now
    handover.courier_arrived_by_id = current_user.id
    handover.courier_arrival_latitude = data.latitude
    handover.courier_arrival_longitude = data.longitude
    handover.courier_arrival_notes = data.notes

    db.add(
        ShipmentTrackingEvent(
            shipment_id=shipment.id,
            status=shipment.status,
            location=(
                f"{data.latitude},{data.longitude}"
                if data.latitude is not None and data.longitude is not None
                else None
            ),
            notes=data.notes or "Assigned logistics company confirmed courier arrival for pickup",
            created_by_id=current_user.id,
        )
    )

    seller = db.query(Seller).filter(Seller.id == shipment.seller_id).first()
    if seller is not None:
        notification_service.notify(
            db=db,
            user_id=seller.user_id,
            event=NotificationEvent.delivery_updated,
            title="Courier has arrived for pickup",
            message="The assigned logistics courier has arrived. Open the seller order and confirm the physical product handover.",
            data={
                "shipment_id": str(shipment.id),
                "seller_order_id": str(seller_order.id),
                "order_id": str(shipment.order_id),
                "handover_id": str(handover.id),
            },
            action_url=f"/seller/orders/{seller_order.id}",
            commit=False,
        )
    _commit(db)
    db.refresh(handover)
    return handover


@router.get(
    "/me/shipments/{shipment_id}/pickup-proof",
    response_model=PickupProofResponse,
)
def get_logistics_pickup_proof(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.logistics_shipments_read.value)
    ),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")

    proof = (
        db.query(ShipmentPickupProof)
        .filter(
            ShipmentPickupProof.shipment_id == shipment_id,
            ShipmentPickupProof.logistics_company_id == membership.logistics_company_id,
        )
        .first()
    )
    if proof is None:
        raise HTTPException(404, "Pickup proof not found")
    return proof


@router.post(
    "/me/shipments/{shipment_id}/pickup-proof",
    response_model=PickupProofResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_logistics_pickup_proof(
    shipment_id: UUID,
    photo: UploadFile = File(...),
    latitude: Decimal = Form(...),
    longitude: Decimal = Form(...),
    courier_reference: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.logistics_shipments_update.value)
    ),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")

    if latitude < Decimal("-90") or latitude > Decimal("90"):
        raise HTTPException(422, "latitude must be between -90 and 90")
    if longitude < Decimal("-180") or longitude > Decimal("180"):
        raise HTTPException(422, "longitude must be between -180 and 180")

    shipment = (
        db.query(Shipment)
        .options(joinedload(Shipment.order))
        .filter(
            Shipment.id == shipment_id,
            Shipment.logistics_company_id == membership.logistics_company_id,
        )
        .with_for_update()
        .first()
    )
    if shipment is None:
        raise HTTPException(404, "Shipment not found for this logistics company")

    existing = (
        db.query(ShipmentPickupProof)
        .filter(ShipmentPickupProof.shipment_id == shipment.id)
        .first()
    )
    if existing:
        return existing

    handover = (
        db.query(ShipmentHandover)
        .filter(ShipmentHandover.shipment_id == shipment.id)
        .first()
    )
    if handover is None:
        raise HTTPException(409, "Shipment handover record is missing")

    try:
        image = await store_pickup_proof_image(photo, shipment_id=shipment.id)
        proof = create_pickup_proof(
            db,
            shipment=shipment,
            handover=handover,
            customer_id=shipment.order.user_id,
            logistics_company_id=membership.logistics_company_id,
            uploaded_by_id=current_user.id,
            image=image,
            latitude=latitude,
            longitude=longitude,
            courier_reference=courier_reference,
            notes=notes,
        )
        return proof
    except PickupProofError as exc:
        db.rollback()
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


@router.post(
    "/me/shipments/{shipment_id}/events",
    response_model=ShipmentResponse,
)
def update_company_shipment(
    shipment_id: UUID,
    data: ShipmentTrackingEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.logistics_shipments_update.value)
    ),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")

    shipment = (
        db.query(Shipment)
        .options(
            selectinload(Shipment.items),
            selectinload(Shipment.tracking_events),
            joinedload(Shipment.order),
        )
        .filter(
            Shipment.id == shipment_id,
            Shipment.logistics_company_id == membership.logistics_company_id,
        )
        .with_for_update()
        .first()
    )
    if not shipment:
        raise HTTPException(404, "Shipment not found for this logistics company")

    allowed = ALLOWED_LOGISTICS_TRANSITIONS.get(shipment.status, set())
    if data.status == ShipmentStatus.delivered:
        raise HTTPException(409, "Delivered status requires customer OTP proof of delivery")
    if data.status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Invalid shipment transition: {shipment.status.value} -> {data.status.value}",
        )

    if data.tracking_number:
        duplicate = (
            db.query(Shipment.id)
            .filter(
                Shipment.tracking_number == data.tracking_number,
                Shipment.id != shipment.id,
            )
            .first()
        )
        if duplicate:
            raise HTTPException(409, "Tracking number is already in use")
        shipment.tracking_number = data.tracking_number.strip()

    if data.carrier_name:
        shipment.carrier_name = data.carrier_name.strip()

    shipment.status = data.status

    now = datetime.now(timezone.utc)
    if data.status == ShipmentStatus.dispatched and shipment.dispatched_at is None:
        shipment.dispatched_at = now

    db.add(
        ShipmentTrackingEvent(
            shipment_id=shipment.id,
            status=data.status,
            location=data.location,
            notes=data.notes,
            created_by_id=current_user.id,
        )
    )
    _commit(db)
    db.refresh(shipment)
    return shipment


PICKUP_JOB_TRANSITIONS = {
    PickupJobStatus.scheduled: {PickupJobStatus.assigned, PickupJobStatus.cancelled},
    PickupJobStatus.assigned: {PickupJobStatus.en_route, PickupJobStatus.cancelled},
    PickupJobStatus.en_route: {PickupJobStatus.arrived, PickupJobStatus.failed},
    PickupJobStatus.arrived: {PickupJobStatus.completed, PickupJobStatus.failed},
    PickupJobStatus.failed: {PickupJobStatus.assigned, PickupJobStatus.cancelled},
}


@router.get(
    "/me/pickup-jobs", response_model=PaginatedLogisticsPickupJobResponse
)
def my_company_pickup_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: PickupJobStatus | None = Query(None, alias="status"),
    assigned_to_me: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    query = db.query(LogisticsPickupJob).filter(
        LogisticsPickupJob.logistics_company_id == membership.logistics_company_id
    )
    if status_filter:
        query = query.filter(LogisticsPickupJob.status == status_filter)
    if assigned_to_me:
        query = query.filter(LogisticsPickupJob.assigned_membership_id == membership.id)
    total = query.count()
    rows = query.order_by(LogisticsPickupJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "total_pages": _pages(total, page_size), "results": rows}


@router.post(
    "/me/shipments/{shipment_id}/pickup-job",
    response_model=LogisticsPickupJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_pickup_job(
    shipment_id: UUID,
    data: LogisticsPickupJobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(membership, LogisticsCompanyPermission.pickups_manage)
    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id,
        Shipment.logistics_company_id == membership.logistics_company_id,
    ).with_for_update().first()
    if not shipment:
        raise HTTPException(404, "Shipment not found for this logistics company")
    if shipment.status != ShipmentStatus.ready_for_dispatch:
        raise HTTPException(409, "Pickup job requires a shipment ready for dispatch")
    existing = db.query(LogisticsPickupJob).filter(LogisticsPickupJob.shipment_id == shipment.id).first()
    if existing:
        return existing
    assigned = None
    if data.assigned_membership_id:
        assigned = db.query(LogisticsCompanyUser).filter(
            LogisticsCompanyUser.id == data.assigned_membership_id,
            LogisticsCompanyUser.logistics_company_id == membership.logistics_company_id,
            LogisticsCompanyUser.is_active.is_(True),
        ).first()
        if not assigned:
            raise HTTPException(404, "Active company member not found")
    now = datetime.now(timezone.utc)
    job = LogisticsPickupJob(
        logistics_company_id=membership.logistics_company_id,
        shipment_id=shipment.id,
        assigned_membership_id=data.assigned_membership_id,
        status=PickupJobStatus.assigned if assigned else PickupJobStatus.scheduled,
        scheduled_for=data.scheduled_for,
        pickup_reference=f"PU-{uuid4().hex[:12].upper()}",
        dispatcher_notes=data.dispatcher_notes,
        assigned_at=now if assigned else None,
        created_by_id=current_user.id,
    )
    db.add(job); _commit(db); db.refresh(job); return job


@router.patch(
    "/me/pickup-jobs/{job_id}/assign",
    response_model=LogisticsPickupJobResponse,
)
def assign_pickup_job(
    job_id: UUID,
    data: LogisticsPickupJobAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    _require_company_permission(membership, LogisticsCompanyPermission.pickups_manage)
    job = db.query(LogisticsPickupJob).filter(
        LogisticsPickupJob.id == job_id,
        LogisticsPickupJob.logistics_company_id == membership.logistics_company_id,
    ).with_for_update().first()
    if not job:
        raise HTTPException(404, "Pickup job not found")
    if job.status in {PickupJobStatus.completed, PickupJobStatus.cancelled}:
        raise HTTPException(409, "Closed pickup job cannot be reassigned")
    assigned = db.query(LogisticsCompanyUser).filter(
        LogisticsCompanyUser.id == data.assigned_membership_id,
        LogisticsCompanyUser.logistics_company_id == membership.logistics_company_id,
        LogisticsCompanyUser.is_active.is_(True),
    ).first()
    if not assigned:
        raise HTTPException(404, "Active company member not found")
    job.assigned_membership_id = assigned.id
    job.status = PickupJobStatus.assigned
    job.assigned_at = datetime.now(timezone.utc)
    if data.scheduled_for is not None: job.scheduled_for = data.scheduled_for
    if data.dispatcher_notes is not None: job.dispatcher_notes = data.dispatcher_notes
    job.failure_reason = None
    _commit(db); db.refresh(job); return job


@router.post(
    "/me/pickup-jobs/{job_id}/status",
    response_model=LogisticsPickupJobResponse,
)
def update_pickup_job_status(
    job_id: UUID,
    data: LogisticsPickupJobStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = _membership_for_user(db, current_user.id)
    if not membership:
        raise HTTPException(403, "User is not linked to a logistics company")
    job = db.query(LogisticsPickupJob).filter(
        LogisticsPickupJob.id == job_id,
        LogisticsPickupJob.logistics_company_id == membership.logistics_company_id,
    ).with_for_update().first()
    if not job:
        raise HTTPException(404, "Pickup job not found")
    can_dispatch = LogisticsCompanyPermission.pickups_manage in _effective_company_permissions(membership)
    if job.assigned_membership_id != membership.id and not can_dispatch:
        raise HTTPException(403, "Pickup job is assigned to another company member")
    allowed = PICKUP_JOB_TRANSITIONS.get(job.status, set())
    if data.status not in allowed:
        raise HTTPException(409, f"Invalid pickup transition: {job.status.value} -> {data.status.value}")
    shipment = db.query(Shipment).filter(Shipment.id == job.shipment_id).with_for_update().one()
    now = datetime.now(timezone.utc)
    job.status = data.status
    job.courier_notes = data.notes
    job.failure_reason = data.failure_reason
    if data.status == PickupJobStatus.en_route:
        job.started_at = now
    elif data.status == PickupJobStatus.arrived:
        job.arrived_at = now

        # F4: the pickup-job arrival is the operational source of courier arrival.
        # Keep the seller handover checkpoint synchronized so the Seller UI can
        # immediately unlock "Confirm Product Handover".
        seller_order = (
            db.query(SellerOrder)
            .filter(
                SellerOrder.order_id == shipment.order_id,
                SellerOrder.seller_id == shipment.seller_id,
                SellerOrder.store_id == shipment.store_id,
            )
            .first()
        )
        if seller_order is None:
            db.rollback()
            raise HTTPException(409, "Seller order is missing for this shipment")

        handover = (
            db.query(ShipmentHandover)
            .filter(ShipmentHandover.shipment_id == shipment.id)
            .with_for_update()
            .first()
        )
        if handover is None:
            handover = ensure_shipment_handover(
                db, seller_order=seller_order, shipment=shipment
            )

        if handover.status != "seller_confirmed" and handover.courier_arrived_at is None:
            handover.status = "courier_arrived"
            handover.courier_arrived_at = now
            handover.courier_arrived_by_id = current_user.id
            handover.courier_arrival_notes = data.notes

            db.add(
                ShipmentTrackingEvent(
                    shipment_id=shipment.id,
                    status=shipment.status,
                    notes=data.notes or "Assigned logistics courier arrived for seller pickup",
                    created_by_id=current_user.id,
                )
            )

            seller = db.query(Seller).filter(Seller.id == shipment.seller_id).first()
            if seller is not None:
                notification_service.notify(
                    db=db,
                    user_id=seller.user_id,
                    event=NotificationEvent.delivery_updated,
                    title="Courier has arrived for pickup",
                    message="The assigned logistics courier has arrived. Open the seller order and confirm the physical product handover.",
                    data={
                        "shipment_id": str(shipment.id),
                        "seller_order_id": str(seller_order.id),
                        "order_id": str(shipment.order_id),
                        "handover_id": str(handover.id),
                    },
                    action_url=f"/seller/orders/{seller_order.id}",
                    commit=False,
                )
    elif data.status == PickupJobStatus.cancelled:
        job.cancelled_at = now
    elif data.status == PickupJobStatus.completed:
        handover = (
            db.query(ShipmentHandover)
            .filter(ShipmentHandover.shipment_id == shipment.id)
            .with_for_update()
            .first()
        )
        if not handover or handover.status != "seller_confirmed":
            db.rollback()
            raise HTTPException(409, "Seller must confirm shipment handover before pickup completion")

        pickup_proof = (
            db.query(ShipmentPickupProof)
            .filter(ShipmentPickupProof.shipment_id == shipment.id)
            .first()
        )
        if pickup_proof is None:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "pickup_proof_required",
                    "message": "Upload the pickup proof photo before completing the pickup job.",
                },
            )

        job.completed_at = now
        shipment.status = ShipmentStatus.dispatched
        shipment.dispatched_at = shipment.dispatched_at or now
        db.add(ShipmentTrackingEvent(
            shipment_id=shipment.id,
            status=ShipmentStatus.dispatched,
            notes=data.notes or "Pickup completed after seller handover and pickup proof",
            created_by_id=current_user.id,
        ))
    _commit(db); db.refresh(job); return job
    
    
@router.get(
    "/eligible",
    response_model=list[LogisticsCompanyResponse],
)
def get_eligible_logistics_companies(
    city: str = Query(...),
    region: str | None = Query(None),
    country: str | None = Query(None),
    scope: LogisticsScope = Query(LogisticsScope.local),
    db: Session = Depends(get_db),
):
    """Find active logistics companies that cover the delivery address."""
    query = db.query(LogisticsCompany).filter(
        LogisticsCompany.status == LogisticsCompanyStatus.active,
        LogisticsCompany.scope == scope,
    )
    
    # Join with zones to match coverage
    query = query.join(
        ShippingZone,
        ShippingZone.logistics_company_id == LogisticsCompany.id,
    ).filter(
        ShippingZone.is_active.is_(True),
    )
    
    # Match by city or entire country coverage
    zone_filter = or_(
        ShippingZone.cities.icontains(city),
        ShippingZone.covers_entire_country.is_(True),
    )
    if region:
        zone_filter = or_(zone_filter, ShippingZone.regions.icontains(region))
    
    query = query.filter(zone_filter)
    
    # Ensure company has active services and rates
    query = query.join(
        ShippingMethod,
        ShippingMethod.logistics_company_id == LogisticsCompany.id,
    ).filter(ShippingMethod.is_active.is_(True))
    
    query = query.join(
        ShippingRate,
        ShippingRate.method_id == ShippingMethod.id,
    ).filter(ShippingRate.is_active.is_(True))
    
    companies = query.distinct().all()
    return companies

# F2 — Logistics participation in the same public seller-order conversation.
def _company_shipment_and_seller_order(
    db: Session, *, shipment_id: UUID, user_id: UUID
) -> tuple[Shipment, SellerOrder, LogisticsCompanyUser]:
    membership = _membership_for_user(db, user_id)
    if not membership:
        raise HTTPException(status_code=403, detail="User is not linked to a logistics company")
    shipment = (
        db.query(Shipment)
        .filter(
            Shipment.id == shipment_id,
            Shipment.logistics_company_id == membership.logistics_company_id,
        )
        .first()
    )
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    seller_order = (
        db.query(SellerOrder)
        .filter(
            SellerOrder.order_id == shipment.order_id,
            SellerOrder.seller_id == shipment.seller_id,
            SellerOrder.store_id == shipment.store_id,
        )
        .first()
    )
    if not seller_order:
        raise HTTPException(status_code=404, detail="Seller order conversation not found")
    return shipment, seller_order, membership


@router.get(
    "/me/shipments/{shipment_id}/messages",
    response_model=list[SellerOrderMessageResponse],
)
def logistics_shipment_messages(
    shipment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.logistics_shipments_read.value)
    ),
):
    _, seller_order, _ = _company_shipment_and_seller_order(
        db, shipment_id=shipment_id, user_id=current_user.id
    )
    return (
        db.query(SellerOrderMessage)
        .options(selectinload(SellerOrderMessage.attachments))
        .filter(
            SellerOrderMessage.seller_order_id == seller_order.id,
            SellerOrderMessage.is_internal.is_(False),
        )
        .order_by(SellerOrderMessage.created_at.asc())
        .all()
    )


@router.post(
    "/me/shipments/{shipment_id}/messages",
    response_model=SellerOrderMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def logistics_send_shipment_message(
    shipment_id: UUID,
    data: SellerOrderMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.logistics_shipments_update.value)
    ),
):
    _, seller_order, membership = _company_shipment_and_seller_order(
        db, shipment_id=shipment_id, user_id=current_user.id
    )
    _require_company_permission(membership, LogisticsCompanyPermission.shipments_manage)
    if data.is_internal:
        raise HTTPException(status_code=400, detail="Logistics cannot create internal seller notes")
    message = SellerOrderMessage(
        seller_order_id=seller_order.id,
        sender_user_id=current_user.id,
        sender_role_label="logistics",
        message=data.message.strip(),
        is_internal=False,
    )
    db.add(message)
    db.flush()
    for url in data.attachment_urls:
        db.add(SellerOrderMessageAttachment(message_id=message.id, file_url=url))
    db.commit()
    return (
        db.query(SellerOrderMessage)
        .options(selectinload(SellerOrderMessage.attachments))
        .filter(SellerOrderMessage.id == message.id)
        .one()
    )
