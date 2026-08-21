from datetime import datetime, timezone
import hashlib

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from api.deps import get_db
from api.enums import AdvertisementPlacement, AdvertisementStatus
from api.models import Advertisement, AdvertisementEngagementEvent
from api.schemas import (
    PublicAdvertisementResponse,
    PublicAdvertisementSlotResponse,
    AdvertisementTrackingRequest,
    AdvertisementTrackingResponse,
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


def _session_hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def _record_engagement(
    db: Session,
    *,
    advertisement: Advertisement,
    event_type: str,
    payload: AdvertisementTrackingRequest,
) -> AdvertisementTrackingResponse:
    """Insert one idempotent event and atomically update aggregate counters."""

    session_hash = _session_hash(payload.session_id)

    if event_type == "impression":
        # Exactly one impression per advertisement per browser session.
        event_key = f"imp:{advertisement.id}:{session_hash}"
    else:
        # Each deliberate click gets a unique browser-generated event id.
        client_event_id = payload.client_event_id or session_hash[:32]
        event_key = f"clk:{advertisement.id}:{client_event_id}"

    insert_stmt = (
        pg_insert(AdvertisementEngagementEvent)
        .values(
            advertisement_id=advertisement.id,
            event_type=event_type,
            placement=advertisement.placement,
            session_hash=session_hash,
            event_key=event_key,
            page_path=payload.page_path,
        )
        .on_conflict_do_nothing(index_elements=[AdvertisementEngagementEvent.event_key])
        .returning(AdvertisementEngagementEvent.id)
    )

    inserted_id = db.execute(insert_stmt).scalar_one_or_none()
    duplicate = inserted_id is None

    if not duplicate:
        if event_type == "impression":
            advertisement.impression_count = Advertisement.impression_count + 1
        else:
            advertisement.click_count = Advertisement.click_count + 1

        db.flush()

    db.commit()
    db.refresh(advertisement)

    return AdvertisementTrackingResponse(
        accepted=True,
        duplicate=duplicate,
        event_type=event_type,
        impression_count=advertisement.impression_count,
        click_count=advertisement.click_count,
    )


def _live_ad_for_tracking(db: Session, advertisement_id):
    now = datetime.now(timezone.utc)
    return _live_query(db, now=now).filter(Advertisement.id == advertisement_id).first()


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


@router.post(
    "/{advertisement_id}/impression",
    response_model=AdvertisementTrackingResponse,
)
def track_advertisement_impression(
    advertisement_id: str,
    payload: AdvertisementTrackingRequest,
    db: Session = Depends(get_db),
):
    """Count a real storefront impression once per browser session.

    The Frontend only calls this after at least 50% of the advertisement has
    remained visible for a short period. Server-side event_key uniqueness is
    the second line of defence against inflated React re-render counts.
    """
    from uuid import UUID

    try:
        ad_id = UUID(advertisement_id)
    except ValueError:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Advertisement not found"
        )

    advertisement = _live_ad_for_tracking(db, ad_id)
    if advertisement is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Advertisement is not currently live",
        )

    return _record_engagement(
        db,
        advertisement=advertisement,
        event_type="impression",
        payload=payload,
    )


@router.post(
    "/{advertisement_id}/click",
    response_model=AdvertisementTrackingResponse,
)
def track_advertisement_click(
    advertisement_id: str,
    payload: AdvertisementTrackingRequest,
    db: Session = Depends(get_db),
):
    """Record an advertisement click before/while navigation continues."""
    from uuid import UUID

    try:
        ad_id = UUID(advertisement_id)
    except ValueError:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Advertisement not found"
        )

    advertisement = _live_ad_for_tracking(db, ad_id)
    if advertisement is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Advertisement is not currently live",
        )

    return _record_engagement(
        db,
        advertisement=advertisement,
        event_type="click",
        payload=payload,
    )


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

    If no campaign is live, advertisement=null. The Frontend can then render
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
                _public_ad(winners[placement]) if placement in winners else None
            ),
        }
        for placement in requested
    ]
