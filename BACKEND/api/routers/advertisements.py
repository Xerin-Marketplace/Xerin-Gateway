from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import (
    AdvertisementPlacement,
    AdvertisementStatus,
    PermissionCode,
)
from api.models import Advertisement, AdminActivityLog, User
from api.permissions import require_permission
from api.schemas import (
    AdvertisementActionResponse,
    AdvertisementCreate,
    AdvertisementResponse,
    AdvertisementUpdate,
    PaginatedAdvertisementResponse,
)


router = APIRouter(
    prefix="/admin/advertisements",
    tags=["Admin Advertisements"],
)


def _effective_status(ad: Advertisement, now: datetime | None = None) -> str:
    return ad.effective_status(now or datetime.now(timezone.utc))


def _serialize(ad: Advertisement) -> AdvertisementResponse:
    return AdvertisementResponse(
        id=ad.id,
        advertiser_name=ad.advertiser_name,
        title=ad.title,
        description=ad.description,
        image_url=ad.image_url,
        mobile_image_url=ad.mobile_image_url,
        alt_text=ad.alt_text,
        target_url=ad.target_url,
        cta_label=ad.cta_label,
        placement=ad.placement,
        status=ad.status,
        effective_status=_effective_status(ad),
        starts_at=ad.starts_at,
        ends_at=ad.ends_at,
        priority=ad.priority,
        billing_type=ad.billing_type,
        price=ad.price,
        currency=ad.currency,
        impression_count=ad.impression_count,
        click_count=ad.click_count,
        metadata_json=ad.metadata_json or {},
        created_by_id=ad.created_by_id,
        updated_by_id=ad.updated_by_id,
        created_at=ad.created_at,
        updated_at=ad.updated_at,
    )


def _audit(
    db: Session,
    *,
    current_user: User,
    action: str,
    ad: Advertisement,
    details: dict | None = None,
) -> None:
    db.add(
        AdminActivityLog(
            admin_user_id=current_user.id,
            action=action,
            resource_type="advertisement",
            resource_id=str(ad.id),
            details=details or {},
        )
    )


def _get_ad(db: Session, advertisement_id: UUID, *, lock: bool = False) -> Advertisement:
    query = db.query(Advertisement).filter(Advertisement.id == advertisement_id)
    if lock:
        query = query.with_for_update()
    ad = query.first()
    if not ad:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Advertisement not found",
        )
    return ad


def _validate_merged_schedule(
    ad: Advertisement,
    changes: dict,
) -> None:
    starts_at = changes.get("starts_at", ad.starts_at)
    ends_at = changes.get("ends_at", ad.ends_at)
    if starts_at is None or ends_at is None or ends_at <= starts_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="ends_at must be later than starts_at",
        )


@router.get("", response_model=PaginatedAdvertisementResponse)
def list_advertisements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=180),
    placement: AdvertisementPlacement | None = Query(default=None),
    stored_status: AdvertisementStatus | None = Query(default=None),
    effective_status: str | None = Query(
        default=None,
        pattern="^(draft|scheduled|active|paused|expired)$",
    ),
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.advertisements_read.value)
    ),
):
    query = db.query(Advertisement)
    now = datetime.now(timezone.utc)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Advertisement.title.ilike(term),
                Advertisement.advertiser_name.ilike(term),
                Advertisement.description.ilike(term),
            )
        )

    if placement is not None:
        query = query.filter(Advertisement.placement == placement)

    if stored_status is not None:
        query = query.filter(Advertisement.status == stored_status)

    # Effective status uses the exact current date/time. No scheduler is needed.
    if effective_status == "draft":
        query = query.filter(Advertisement.status == AdvertisementStatus.draft)
    elif effective_status == "paused":
        query = query.filter(Advertisement.status == AdvertisementStatus.paused)
    elif effective_status == "scheduled":
        query = query.filter(
            Advertisement.status == AdvertisementStatus.active,
            Advertisement.starts_at > now,
        )
    elif effective_status == "active":
        query = query.filter(
            Advertisement.status == AdvertisementStatus.active,
            Advertisement.starts_at <= now,
            Advertisement.ends_at > now,
        )
    elif effective_status == "expired":
        query = query.filter(
            Advertisement.status == AdvertisementStatus.active,
            Advertisement.ends_at <= now,
        )

    total = query.count()
    rows = (
        query.order_by(
            Advertisement.created_at.desc(),
            Advertisement.priority.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": 0 if total == 0 else (total + page_size - 1) // page_size,
        "results": [_serialize(row) for row in rows],
    }


@router.get("/{advertisement_id}", response_model=AdvertisementResponse)
def get_advertisement(
    advertisement_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.advertisements_read.value)
    ),
):
    return _serialize(_get_ad(db, advertisement_id))


@router.post(
    "",
    response_model=AdvertisementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_advertisement(
    data: AdvertisementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.advertisements_manage.value)
    ),
):
    ad = Advertisement(
        **data.model_dump(),
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )
    db.add(ad)
    db.flush()

    _audit(
        db,
        current_user=current_user,
        action="create_advertisement",
        ad=ad,
        details={
            "title": ad.title,
            "advertiser_name": ad.advertiser_name,
            "placement": ad.placement.value,
            "status": ad.status.value,
            "starts_at": ad.starts_at.isoformat(),
            "ends_at": ad.ends_at.isoformat(),
        },
    )

    db.commit()
    db.refresh(ad)
    return _serialize(ad)


@router.patch("/{advertisement_id}", response_model=AdvertisementResponse)
def update_advertisement(
    advertisement_id: UUID,
    data: AdvertisementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.advertisements_manage.value)
    ),
):
    ad = _get_ad(db, advertisement_id, lock=True)
    changes = data.model_dump(exclude_unset=True)

    _validate_merged_schedule(ad, changes)

    changed_fields: list[str] = []
    for key, value in changes.items():
        if getattr(ad, key) != value:
            setattr(ad, key, value)
            changed_fields.append(key)

    ad.updated_by_id = current_user.id

    _audit(
        db,
        current_user=current_user,
        action="update_advertisement",
        ad=ad,
        details={"changed_fields": sorted(changed_fields)},
    )

    db.commit()
    db.refresh(ad)
    return _serialize(ad)


@router.post(
    "/{advertisement_id}/activate",
    response_model=AdvertisementActionResponse,
)
def activate_advertisement(
    advertisement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.advertisements_manage.value)
    ),
):
    ad = _get_ad(db, advertisement_id, lock=True)
    now = datetime.now(timezone.utc)

    if ad.ends_at <= now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Expired advertisement cannot be activated. Extend ends_at first.",
        )

    ad.status = AdvertisementStatus.active
    ad.updated_by_id = current_user.id

    _audit(
        db,
        current_user=current_user,
        action="activate_advertisement",
        ad=ad,
        details={
            "starts_at": ad.starts_at.isoformat(),
            "ends_at": ad.ends_at.isoformat(),
        },
    )

    db.commit()
    db.refresh(ad)

    effective = _effective_status(ad)
    message = (
        "Advertisement activated and is live now."
        if effective == "active"
        else "Advertisement activated and scheduled for its configured start time."
    )
    return {
        "id": ad.id,
        "status": ad.status,
        "effective_status": effective,
        "message": message,
    }


@router.post(
    "/{advertisement_id}/pause",
    response_model=AdvertisementActionResponse,
)
def pause_advertisement(
    advertisement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.advertisements_manage.value)
    ),
):
    ad = _get_ad(db, advertisement_id, lock=True)
    ad.status = AdvertisementStatus.paused
    ad.updated_by_id = current_user.id

    _audit(
        db,
        current_user=current_user,
        action="pause_advertisement",
        ad=ad,
    )

    db.commit()
    db.refresh(ad)

    return {
        "id": ad.id,
        "status": ad.status,
        "effective_status": _effective_status(ad),
        "message": "Advertisement paused and will not appear on the storefront.",
    }


@router.delete(
    "/{advertisement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_advertisement(
    advertisement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.advertisements_manage.value)
    ),
):
    ad = _get_ad(db, advertisement_id, lock=True)

    # Audit before deletion; resource_id remains useful after the ad row is gone.
    _audit(
        db,
        current_user=current_user,
        action="delete_advertisement",
        ad=ad,
        details={
            "title": ad.title,
            "advertiser_name": ad.advertiser_name,
            "placement": ad.placement.value,
            "impression_count": ad.impression_count,
            "click_count": ad.click_count,
        },
    )
    db.delete(ad)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
