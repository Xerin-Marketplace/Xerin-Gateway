from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from api.deps import get_current_user, get_db
from api.enums import (
    LogisticsCompanyStatus,
    LogisticsCompanyPermission,
    LogisticsMemberRole,
    MultiSellerPricingStrategy,
    LogisticsScope,
    PermissionCode,
    ShipmentStatus,
)
from api.models import (
    LogisticsCompany,
    LogisticsCompanyUser,
    LogisticsIntegrationConfig,
    SellerOrder,
    Shipment,
    ShipmentHandover,
    ShipmentPickupProof,
    ShipmentTrackingEvent,
    ShippingMethod,
    ShippingRate,
    ShippingZone,
    User,
)
from api.permissions import get_user_permissions, require_permission
from api.services.seller_handover import ensure_shipment_handover
from api.services.pickup_proof_service import (
    PickupProofError,
    create_pickup_proof,
    store_pickup_proof_image,
)
from api.schemas import (
    LogisticsCompanyCreate,
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
    LogisticsCourierArrivalRequest,
    LogisticsPricingSettingsResponse,
    LogisticsPricingSettingsUpdate,
    PaginatedLogisticsCompanyResponse,
    PaginatedShipmentResponse,
    PaginatedShippingMethodResponse,
    PaginatedShippingRateResponse,
    PaginatedShippingZoneResponse,
    ShipmentResponse,
    ShipmentHandoverResponse,
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

router = APIRouter(prefix="/logistics", tags=["Logistics"])


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
        ShipmentStatus.delivered,
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
    if data.status == ShipmentStatus.delivered and shipment.delivered_at is None:
        shipment.delivered_at = now

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
