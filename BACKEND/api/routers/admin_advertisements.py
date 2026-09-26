"""Admin advertisement management — CRUD, activation, image upload, analytics."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from PIL import Image
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session
from uuid import UUID

from api.config import settings
from api.deps import get_db
from api.permissions import require_permission
from api.enums import PermissionCode
from api.models import Advertisement, AdvertisementEvent, User
from api.schemas import (
    AdvertisementCreate,
    AdvertisementResponse,
    AdvertisementUpdate,
    PaginatedAdvertisementResponse,
)
from api.services.product_image_service import _prepare_image, _public_url, _safe_original_filename

router = APIRouter(prefix="/admin/advertisements", tags=["Admin - Advertisements"])

READ = PermissionCode.advertisements_read.value
MANAGE = PermissionCode.advertisements_manage.value

PLACEMENTS = {
    "hero_side_top", "hero_side_bottom", "homepage_banner",
    "category_banner", "search_banner",
}
STORED_STATUSES = {"draft", "active", "paused"}


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


def _response(ad: Advertisement) -> AdvertisementResponse:
    data = {
        c.name: getattr(ad, c.name) for c in Advertisement.__table__.columns
    }
    data["effective_status"] = _effective_status(ad, datetime.now(timezone.utc))
    data["price"] = float(ad.price) if ad.price is not None else None
    return AdvertisementResponse(**data)


def _get_or_404(db: Session, ad_id: UUID) -> Advertisement:
    ad = db.query(Advertisement).filter(Advertisement.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Advertisement not found")
    return ad


@router.get("", response_model=PaginatedAdvertisementResponse)
def list_advertisements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    placement: str | None = None,
    stored_status: str | None = None,
    effective_status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(READ)),
):
    q = db.query(Advertisement)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(
            (Advertisement.title.ilike(like)) | (Advertisement.advertiser_name.ilike(like))
        )
    if placement in PLACEMENTS:
        q = q.filter(Advertisement.placement == placement)
    if stored_status in STORED_STATUSES:
        q = q.filter(Advertisement.status == stored_status)

    ads = q.order_by(Advertisement.created_at.desc()).all()

    if effective_status:
        now = datetime.now(timezone.utc)
        ads = [a for a in ads if _effective_status(a, now) == effective_status]

    total = len(ads)
    start = (page - 1) * page_size
    return PaginatedAdvertisementResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
        results=[_response(a) for a in ads[start:start + page_size]],
    )


@router.get("/analytics/overview")
def analytics_overview(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(READ)),
):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    ads = db.query(Advertisement).all()

    status_counts = {"total": len(ads), "draft": 0, "scheduled": 0, "active": 0, "paused": 0, "expired": 0}
    for a in ads:
        status_counts[_effective_status(a, now)] += 1

    events = (
        db.query(
            sa_func.date(AdvertisementEvent.created_at).label("day"),
            AdvertisementEvent.event_type,
            sa_func.count(),
        )
        .filter(AdvertisementEvent.created_at >= since)
        .group_by("day", AdvertisementEvent.event_type)
        .all()
    )
    daily: dict[str, dict] = {}
    for day, etype, count in events:
        d = daily.setdefault(str(day), {"date": str(day), "impressions": 0, "clicks": 0})
        d["impressions" if etype == "impression" else "clicks"] = count

    total_impressions = sum(a.impression_count for a in ads)
    total_clicks = sum(a.click_count for a in ads)

    revenue: dict[str, float] = {}
    for a in ads:
        if a.price:
            revenue[a.currency] = revenue.get(a.currency, 0.0) + float(a.price)

    top = sorted(ads, key=lambda a: a.impression_count, reverse=True)[:10]

    advertisers: dict[str, dict] = {}
    for a in ads:
        bucket = advertisers.setdefault(
            a.advertiser_name,
            {"advertiser_name": a.advertiser_name, "campaigns": 0, "impressions": 0, "clicks": 0, "ctr_percent": 0.0, "revenue_by_currency": []},
        )
        bucket["campaigns"] += 1
        bucket["impressions"] += a.impression_count
        bucket["clicks"] += a.click_count
    for bucket in advertisers.values():
        bucket["ctr_percent"] = round(100 * bucket["clicks"] / bucket["impressions"], 2) if bucket["impressions"] else 0.0

    return {
        "generated_at": now,
        "days": days,
        "status_counts": status_counts,
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "ctr_percent": round(100 * total_clicks / total_impressions, 2) if total_impressions else 0.0,
        "revenue_by_currency": [{"currency": c, "estimated_revenue": v} for c, v in revenue.items()],
        "daily_engagement": sorted(daily.values(), key=lambda x: x["date"]),
        "top_campaigns": [
            {
                "id": str(a.id), "advertiser_name": a.advertiser_name, "title": a.title,
                "placement": a.placement, "effective_status": _effective_status(a, now),
                "billing_type": a.billing_type, "price": float(a.price) if a.price else None,
                "currency": a.currency, "impressions": a.impression_count,
                "clicks": a.click_count,
                "ctr_percent": round(100 * a.click_count / a.impression_count, 2) if a.impression_count else 0.0,
                "estimated_revenue": float(a.price) if a.price else 0.0,
                "starts_at": a.starts_at, "ends_at": a.ends_at,
            }
            for a in top
        ],
        "advertisers": list(advertisers.values()),
        "revenue_note": "Estimated revenue is the sum of fixed campaign prices; CPC/CPM billing is not yet settled automatically.",
    }


@router.get("/{advertisement_id}", response_model=AdvertisementResponse)
def get_advertisement(
    advertisement_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(READ)),
):
    return _response(_get_or_404(db, advertisement_id))


@router.post("", response_model=AdvertisementResponse, status_code=201)
def create_advertisement(
    data: AdvertisementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(MANAGE)),
):
    ad = Advertisement(
        **data.model_dump(),
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )
    db.add(ad)
    db.commit()
    db.refresh(ad)
    return _response(ad)


@router.patch("/{advertisement_id}", response_model=AdvertisementResponse)
def update_advertisement(
    advertisement_id: UUID,
    data: AdvertisementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(MANAGE)),
):
    ad = _get_or_404(db, advertisement_id)
    update = data.model_dump(exclude_unset=True)
    for key, value in update.items():
        setattr(ad, key, value)
    ad.updated_by_id = current_user.id
    db.commit()
    db.refresh(ad)
    return _response(ad)


@router.post("/{advertisement_id}/activate")
def activate_advertisement(
    advertisement_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(MANAGE)),
):
    ad = _get_or_404(db, advertisement_id)
    if ad.ends_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail="Cannot activate an expired advertisement")
    ad.status = "active"
    db.commit()
    return {"id": str(ad.id), "status": "active", "effective_status": _effective_status(ad, datetime.now(timezone.utc)), "message": "Advertisement activated"}


@router.post("/{advertisement_id}/pause")
def pause_advertisement(
    advertisement_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(MANAGE)),
):
    ad = _get_or_404(db, advertisement_id)
    ad.status = "paused"
    db.commit()
    return {"id": str(ad.id), "status": "paused", "effective_status": _effective_status(ad, datetime.now(timezone.utc)), "message": "Advertisement paused"}


@router.delete("/{advertisement_id}", status_code=204)
def delete_advertisement(
    advertisement_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(MANAGE)),
):
    ad = _get_or_404(db, advertisement_id)
    db.delete(ad)
    db.commit()


@router.post("/upload-image")
async def upload_advertisement_image(
    file: UploadFile = File(...),
    variant: str = Form("desktop"),
    _: User = Depends(require_permission(MANAGE)),
):
    raw = await file.read()
    image, _detected, mime_type = _prepare_image(raw)

    ad_id = uuid.uuid4()
    relative_dir = Path("advertisements")
    absolute_dir = settings.upload_path / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    name = f"{ad_id}.webp"
    (image.convert("RGBA") if image.mode == "RGBA" else image.convert("RGB")).save(
        absolute_dir / name, format="WEBP", quality=88, method=6
    )
    relative = relative_dir / name

    return {
        "image_url": _public_url(relative),
        "original_filename": _safe_original_filename(file.filename),
        "mime_type": "image/webp",
        "file_size": len(raw),
        "width": image.width,
        "height": image.height,
        "variant": "mobile" if variant == "mobile" else "desktop",
    }
