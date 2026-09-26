"""Public advertisement slots + engagement tracking.

Serves the highest-priority currently-active ad per placement. Tracking is
deduplicated per (ad, session, event_type) so refreshes do not inflate
impression counts.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_db
from api.models import Advertisement, AdvertisementEvent
from api.schemas import (
    AdvertisementTrackRequest,
    AdvertisementTrackResponse,
)

router = APIRouter(prefix="/advertisements", tags=["Advertisements"])

PLACEMENTS = (
    "hero_side_top",
    "hero_side_bottom",
    "homepage_banner",
    "category_banner",
    "search_banner",
)


def _effective_status(ad: Advertisement, now: datetime) -> str:
    if ad.status == "draft":
        return "draft"
    if ad.status == "paused":
        return "paused"
    if ad.ends_at <= now:
        return "expired"
    if ad.starts_at > now:
        return "scheduled"
    return "active"


def _public_payload(ad: Advertisement) -> dict:
    return {
        "id": str(ad.id),
        "advertiser_name": ad.advertiser_name,
        "title": ad.title,
        "description": ad.description,
        "image_url": ad.image_url,
        "mobile_image_url": ad.mobile_image_url,
        "alt_text": ad.alt_text,
        "target_url": ad.target_url,
        "cta_label": ad.cta_label,
        "placement": ad.placement,
        "starts_at": ad.starts_at,
        "ends_at": ad.ends_at,
        "sponsored": True,
    }


@router.get("/slots")
def public_slots(
    placements: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list:
    now = datetime.now(timezone.utc)
    wanted = [p for p in (placements or list(PLACEMENTS)) if p in PLACEMENTS]

    ads = (
        db.query(Advertisement)
        .filter(
            Advertisement.placement.in_(wanted),
            Advertisement.status == "active",
            Advertisement.starts_at <= now,
            Advertisement.ends_at > now,
        )
        .order_by(Advertisement.priority.desc(), Advertisement.created_at.desc())
        .all()
    )

    chosen: dict[str, Advertisement] = {}
    for ad in ads:
        chosen.setdefault(ad.placement, ad)

    return [
        {"placement": p, "advertisement": _public_payload(chosen[p]) if p in chosen else None}
        for p in wanted
    ]


@router.get("/active")
def public_active(db: Session = Depends(get_db)) -> list:
    return [
        slot["advertisement"]
        for slot in public_slots(db=db)
        if slot["advertisement"] is not None
    ]


def _track(ad_id, event_type: str, data: AdvertisementTrackRequest, db: Session) -> AdvertisementTrackResponse:
    ad = db.query(Advertisement).filter(Advertisement.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Advertisement not found")

    now = datetime.now(timezone.utc)
    if _effective_status(ad, now) != "active":
        return AdvertisementTrackResponse(
            accepted=False, duplicate=False, event_type=event_type,
            impression_count=ad.impression_count, click_count=ad.click_count,
        )

    event = AdvertisementEvent(
        advertisement_id=ad.id,
        event_type=event_type,
        session_id=data.session_id,
        client_event_id=data.client_event_id,
        page_path=data.page_path,
    )
    db.add(event)
    try:
        db.flush()
        duplicate = False
    except IntegrityError:
        db.rollback()
        duplicate = True

    if not duplicate:
        if event_type == "impression":
            ad.impression_count += 1
        else:
            ad.click_count += 1
        db.commit()

    return AdvertisementTrackResponse(
        accepted=not duplicate,
        duplicate=duplicate,
        event_type=event_type,
        impression_count=ad.impression_count,
        click_count=ad.click_count,
    )


@router.post("/{advertisement_id}/impression", response_model=AdvertisementTrackResponse)
def track_impression(
    advertisement_id: str,
    data: AdvertisementTrackRequest,
    db: Session = Depends(get_db),
):
    return _track(advertisement_id, "impression", data, db)


@router.post("/{advertisement_id}/click", response_model=AdvertisementTrackResponse)
def track_click(
    advertisement_id: str,
    data: AdvertisementTrackRequest,
    db: Session = Depends(get_db),
):
    return _track(advertisement_id, "click", data, db)
