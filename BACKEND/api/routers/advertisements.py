from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import (
    AdvertisementPlacement,
    AdvertisementStatus,
    PermissionCode,
)
from api.models import Advertisement, AdvertisementEngagementEvent, AdminActivityLog, User
from api.permissions import require_permission
from api.services.advertisement_image_service import store_advertisement_image
from api.schemas import (
    AdvertisementActionResponse,
    AdvertisementAnalyticsOverview,
    AdvertisementCreate,
    AdvertisementImageUploadResponse,
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




def _estimated_ad_revenue(ad: Advertisement, *, now: datetime):
    """Estimated earned advertisement revenue for analytics.

    fixed:
        Count the agreed campaign price once the campaign start time has been
        reached and the row is not a draft.
    cpc:
        click_count * unit price.
    cpm:
        impression_count / 1000 * unit price.

    This is analytics, not a payment-settlement ledger.
    """
    from decimal import Decimal

    price = Decimal(ad.price or 0)
    billing_type = getattr(ad.billing_type, "value", ad.billing_type)

    if billing_type == "fixed":
        if (
            ad.status != AdvertisementStatus.draft
            and ad.starts_at is not None
            and ad.starts_at <= now
        ):
            return price
        return Decimal("0")

    if billing_type == "cpc":
        return price * Decimal(ad.click_count or 0)

    if billing_type == "cpm":
        return (
            price
            * Decimal(ad.impression_count or 0)
            / Decimal("1000")
        )

    return Decimal("0")


def _ctr(impressions: int, clicks: int) -> float:
    if impressions <= 0:
        return 0.0
    return round((clicks / impressions) * 100, 2)

@router.post(
    "/upload-image",
    response_model=AdvertisementImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_advertisement_image(
    variant: str = Query(default="desktop", pattern="^(desktop|mobile)$"),
    file: UploadFile = File(...),
    _: User = Depends(
        require_permission(PermissionCode.advertisements_manage.value)
    ),
):
    stored = await store_advertisement_image(file, variant=variant)
    return {
        "image_url": stored.image_url,
        "original_filename": stored.original_filename,
        "mime_type": stored.mime_type,
        "file_size": stored.file_size,
        "width": stored.width,
        "height": stored.height,
        "variant": variant,
    }


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




@router.get(
    "/analytics/overview",
    response_model=AdvertisementAnalyticsOverview,
)
def advertisement_analytics_overview(
    days: int = Query(default=30, ge=7, le=365),
    top_limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    _: User = Depends(
        require_permission(PermissionCode.advertisements_read.value)
    ),
):
    now = datetime.now(timezone.utc)
    ads = db.query(Advertisement).all()

    status_counts = {
        "total": len(ads),
        "draft": 0,
        "scheduled": 0,
        "active": 0,
        "paused": 0,
        "expired": 0,
    }

    total_impressions = 0
    total_clicks = 0
    revenue_by_currency: dict[str, object] = {}
    campaign_rows = []
    advertiser_rollup: dict[str, dict] = {}

    from decimal import Decimal

    for ad in ads:
        effective = _effective_status(ad, now)
        status_counts[effective] = status_counts.get(effective, 0) + 1

        impressions = int(ad.impression_count or 0)
        clicks = int(ad.click_count or 0)
        total_impressions += impressions
        total_clicks += clicks

        revenue = _estimated_ad_revenue(ad, now=now)
        currency = (ad.currency or "TZS").upper()
        revenue_by_currency[currency] = (
            revenue_by_currency.get(currency, Decimal("0")) + revenue
        )

        campaign_rows.append(
            {
                "id": ad.id,
                "advertiser_name": ad.advertiser_name,
                "title": ad.title,
                "placement": ad.placement,
                "effective_status": effective,
                "billing_type": ad.billing_type,
                "price": ad.price,
                "currency": currency,
                "impressions": impressions,
                "clicks": clicks,
                "ctr_percent": _ctr(impressions, clicks),
                "estimated_revenue": revenue,
                "starts_at": ad.starts_at,
                "ends_at": ad.ends_at,
            }
        )

        advertiser = advertiser_rollup.setdefault(
            ad.advertiser_name,
            {
                "campaigns": 0,
                "impressions": 0,
                "clicks": 0,
                "revenue_by_currency": {},
            },
        )
        advertiser["campaigns"] += 1
        advertiser["impressions"] += impressions
        advertiser["clicks"] += clicks
        advertiser_currency = advertiser["revenue_by_currency"]
        advertiser_currency[currency] = (
            advertiser_currency.get(currency, Decimal("0")) + revenue
        )

    campaign_rows.sort(
        key=lambda row: (
            row["clicks"],
            row["impressions"],
            row["estimated_revenue"],
        ),
        reverse=True,
    )

    since = now - timedelta(days=days - 1)
    daily_rows = (
        db.query(
            func.date(AdvertisementEngagementEvent.created_at).label("event_date"),
            AdvertisementEngagementEvent.event_type,
            func.count(AdvertisementEngagementEvent.id).label("event_count"),
        )
        .filter(AdvertisementEngagementEvent.created_at >= since)
        .group_by(
            func.date(AdvertisementEngagementEvent.created_at),
            AdvertisementEngagementEvent.event_type,
        )
        .order_by(func.date(AdvertisementEngagementEvent.created_at).asc())
        .all()
    )

    daily_map: dict[str, dict[str, int]] = {}
    for offset in range(days):
        day = (since + timedelta(days=offset)).date().isoformat()
        daily_map[day] = {"impressions": 0, "clicks": 0}

    for row in daily_rows:
        day = row.event_date.isoformat()
        if day not in daily_map:
            continue
        if row.event_type == "impression":
            daily_map[day]["impressions"] = int(row.event_count)
        elif row.event_type == "click":
            daily_map[day]["clicks"] = int(row.event_count)

    advertisers = []
    for advertiser_name, values in advertiser_rollup.items():
        impressions = int(values["impressions"])
        clicks = int(values["clicks"])
        advertisers.append(
            {
                "advertiser_name": advertiser_name,
                "campaigns": int(values["campaigns"]),
                "impressions": impressions,
                "clicks": clicks,
                "ctr_percent": _ctr(impressions, clicks),
                "revenue_by_currency": [
                    {
                        "currency": currency,
                        "estimated_revenue": amount,
                    }
                    for currency, amount in sorted(
                        values["revenue_by_currency"].items()
                    )
                ],
            }
        )

    advertisers.sort(
        key=lambda row: (row["clicks"], row["impressions"]),
        reverse=True,
    )

    return {
        "generated_at": now,
        "days": days,
        "status_counts": status_counts,
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "ctr_percent": _ctr(total_impressions, total_clicks),
        "revenue_by_currency": [
            {
                "currency": currency,
                "estimated_revenue": amount,
            }
            for currency, amount in sorted(revenue_by_currency.items())
        ],
        "daily_engagement": [
            {
                "date": day,
                "impressions": counts["impressions"],
                "clicks": counts["clicks"],
            }
            for day, counts in daily_map.items()
        ],
        "top_campaigns": campaign_rows[:top_limit],
        "advertisers": advertisers[:top_limit],
        "revenue_note": (
            "Estimated advertising revenue only. Fixed campaigns count their "
            "configured price after the campaign starts; CPC uses clicks × price; "
            "CPM uses impressions / 1,000 × price. This is not proof of advertiser payment."
        ),
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
