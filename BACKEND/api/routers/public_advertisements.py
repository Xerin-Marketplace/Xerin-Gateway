from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import AdvertisementPlacement, AdvertisementStatus
from api.models import Advertisement
from api.schemas import (
    PublicAdvertisementResponse,
    PublicAdvertisementSlotResponse,
)


router = APIRouter(
    prefix="/advertisements",
    tags=["Advertisements"],
)


def _live_query(db: Session, *, now: datetime):
    """Single source of truth for storefront advertisement visibility.

    A campaign is visible only when it is stored as active AND the current
    timezone-aware instant is inside [starts_at, ends_at). At ends_at exactly,
    it disappears without a cron job or status mutation.
    """
    return db.query(Advertisement).filter(
        Advertisement.status == AdvertisementStatus.active,
        Advertisement.starts_at <= now,
        Advertisement.ends_at > now,
    )


def _public_ad(ad: Advertisement) -> PublicAdvertisementResponse:
    return PublicAdvertisementResponse(
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
        starts_at=ad.starts_at,
        ends_at=ad.ends_at,
        sponsored=True,
    )


def _no_stale_ad_cache(response: Response) -> None:
    # Exact start/end times matter. Do not let a browser/CDN retain an ad after
    # ends_at or hide a newly-started campaign behind a stale cached response.
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"


@router.get(
    "/active",
    response_model=list[PublicAdvertisementResponse],
)
def active_advertisements(
    response: Response,
    placement: AdvertisementPlacement | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Return only advertisements that are live at the current instant.

    No authentication is required because this is storefront content.
    """
    now = datetime.now(timezone.utc)
    query = _live_query(db, now=now)

    if placement is not None:
        query = query.filter(Advertisement.placement == placement)

    rows = (
        query.order_by(
            Advertisement.priority.desc(),
            Advertisement.created_at.desc(),
        )
        .limit(limit)
        .all()
    )

    _no_stale_ad_cache(response)
    return [_public_ad(row) for row in rows]


@router.get(
    "/slot/{placement}",
    response_model=PublicAdvertisementSlotResponse,
)
def active_advertisement_slot(
    placement: AdvertisementPlacement,
    response: Response,
    db: Session = Depends(get_db),
):
    """Return the winning live ad for one storefront placement.

    If no campaign is live, advertisement=null. The frontend can then render
    the existing Xerin template/fallback card without any special error state.
    """
    now = datetime.now(timezone.utc)

    ad = (
        _live_query(db, now=now)
        .filter(Advertisement.placement == placement)
        .order_by(
            Advertisement.priority.desc(),
            Advertisement.created_at.desc(),
        )
        .first()
    )

    _no_stale_ad_cache(response)
    return {
        "placement": placement,
        "advertisement": _public_ad(ad) if ad is not None else None,
    }


@router.get(
    "/slots",
    response_model=list[PublicAdvertisementSlotResponse],
)
def active_advertisement_slots(
    response: Response,
    placements: list[AdvertisementPlacement] = Query(
        default=[
            AdvertisementPlacement.hero_side_top,
            AdvertisementPlacement.hero_side_bottom,
        ]
    ),
    db: Session = Depends(get_db),
):
    """Resolve several storefront slots in one request.

    This is intended for the homepage so its two sponsored positions do not
    require two separate API requests. Missing placements return null.
    """
    # Remove duplicates while retaining request order.
    requested = list(dict.fromkeys(placements))
    if not requested:
        _no_stale_ad_cache(response)
        return []

    now = datetime.now(timezone.utc)
    rows = (
        _live_query(db, now=now)
        .filter(Advertisement.placement.in_(requested))
        .order_by(
            Advertisement.placement.asc(),
            Advertisement.priority.desc(),
            Advertisement.created_at.desc(),
        )
        .all()
    )

    winners: dict[AdvertisementPlacement, Advertisement] = {}
    for row in rows:
        winners.setdefault(row.placement, row)

    _no_stale_ad_cache(response)
    return [
        {
            "placement": placement,
            "advertisement": (
                _public_ad(winners[placement])
                if placement in winners
                else None
            ),
        }
        for placement in requested
    ]
