"""Marketing & customer engagement — templates, campaigns, segments,
holiday calendar, monthly automation, and unsubscribe."""
import uuid
from datetime import datetime, time, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from api.enums import PermissionCode
from api.models import (
    MarketingAutomation,
    MarketingCampaign,
    MarketingEvent,
    MarketingMessage,
    MarketingPreference,
    MarketingTemplate,
    Order,
    User,
    UserStatus,
)
from api.permissions import require_permission
from api.services import marketing_service as svc

router = APIRouter(tags=["Marketing"])
admin = APIRouter(prefix="/admin/marketing", tags=["Marketing Admin"])

READ = require_permission(PermissionCode.marketing_read.value)
MANAGE = require_permission(PermissionCode.marketing_manage.value)
APPROVE = require_permission(PermissionCode.marketing_approve.value)


# ------------------------------------------------------------------- helpers
def _template(t: MarketingTemplate) -> dict:
    return {
        "id": str(t.id), "key": t.key, "name": t.name, "purpose": t.purpose,
        "channel": t.channel, "language": t.language, "subject": t.subject,
        "body": t.body, "variables": t.variables or [], "is_approved": t.is_approved,
        "version": t.version,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _campaign(c: MarketingCampaign) -> dict:
    return {
        "id": str(c.id), "name": c.name, "description": c.description,
        "channel": c.channel, "status": c.status, "segment_key": c.segment_key,
        "subject": c.subject, "body": c.body, "template_id": str(c.template_id) if c.template_id else None,
        "scheduled_at": c.scheduled_at.isoformat() if c.scheduled_at else None,
        "approved_at": c.approved_at.isoformat() if c.approved_at else None,
        "sent_at": c.sent_at.isoformat() if c.sent_at else None,
        "stats": c.stats or {},
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _message(m: MarketingMessage) -> dict:
    return {
        "id": str(m.id), "recipient": m.recipient, "channel": m.channel,
        "status": m.status, "error": m.error, "attempts": m.attempts,
        "sent_at": m.sent_at.isoformat() if m.sent_at else None,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _event(e: MarketingEvent, year: int) -> dict:
    d = svc.event_date(e, year)
    return {
        "id": str(e.id), "name": e.name, "rule_type": e.rule_type,
        "jurisdiction": e.jurisdiction, "category": e.category,
        "is_estimated": e.is_estimated, "lead_days": e.lead_days,
        "suggested_email": e.suggested_email, "suggested_sms": e.suggested_sms,
        "is_enabled": e.is_enabled,
        "date_this_year": d.isoformat() if d else None,
    }


# ------------------------------------------------------------------ overview
@admin.get("/overview")
def marketing_overview(
    db: Session = Depends(get_db),
    _: User = Depends(READ),
):
    now = datetime.now(timezone.utc)
    total_users = db.query(User).filter(User.status == UserStatus.active).count()
    prefs = {p.user_id: p for p in db.query(MarketingPreference).all()}
    email_ok = sms_ok = opted_out = 0
    for u in db.query(User).filter(User.status == UserStatus.active).all():
        p = prefs.get(u.id)
        email_on = p.email_marketing if p else True
        sms_on = p.sms_marketing if p else True
        if email_on and u.email:
            email_ok += 1
        if sms_on and u.phone:
            sms_ok += 1
        if p and (not p.email_marketing or not p.sms_marketing):
            opted_out += 1

    campaigns = db.query(MarketingCampaign).all()
    status_counts = {}
    for c in campaigns:
        status_counts[c.status] = status_counts.get(c.status, 0) + 1

    msgs = db.query(
        MarketingMessage.channel,
        MarketingMessage.status,
        func.count(MarketingMessage.id),
    ).group_by(MarketingMessage.channel, MarketingMessage.status).all()
    delivery = {"email": {"sent": 0, "failed": 0, "queued": 0, "skipped": 0},
                "sms": {"sent": 0, "failed": 0, "queued": 0, "skipped": 0}}
    for channel, status, count in msgs:
        delivery.setdefault(channel, {}).setdefault(status, 0)
        delivery[channel][status] += count

    events = db.query(MarketingEvent).filter(MarketingEvent.is_enabled.is_(True)).all()
    upcoming = sorted(
        ({"name": e.name, "date": (svc.event_date(e, now.year) or svc.event_date(e, now.year + 1)), "estimated": e.is_estimated}
         for e in events),
        key=lambda x: x["date"] or datetime.max.date(),
    )[:6]

    return {
        "contacts": {
            "total_customers": total_users,
            "email_eligible": email_ok,
            "sms_eligible": sms_ok,
            "opted_out": opted_out,
        },
        "campaigns": status_counts,
        "delivery": delivery,
        "upcoming_events": [{"name": e["name"], "date": e["date"].isoformat() if e["date"] else None,
                              "estimated": e["estimated"]} for e in upcoming],
    }


# ------------------------------------------------------------------ segments
@admin.get("/segments")
def marketing_segments(
    channel: str = Query("email", pattern="^(email|sms)$"),
    db: Session = Depends(get_db),
    _: User = Depends(READ),
):
    return [
        {"key": key, "label": label, "estimated_recipients": len(svc.audience(db, key, channel))}
        for key, label in svc.SEGMENTS.items()
    ]


# ------------------------------------------------------------------ templates
class TemplateIn(BaseModel):
    key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9_\-]+$")
    name: str = Field(min_length=2, max_length=180)
    purpose: str | None = None
    channel: str = Field(pattern="^(email|sms)$")
    language: str = Field(default="en", max_length=5)
    subject: str | None = None
    body: str = Field(min_length=1)
    variables: list[str] | None = None


@admin.get("/templates")
def list_templates(channel: str | None = None, db: Session = Depends(get_db), _: User = Depends(READ)):
    q = db.query(MarketingTemplate).order_by(MarketingTemplate.name)
    if channel:
        q = q.filter(MarketingTemplate.channel == channel)
    return [_template(t) for t in q.all()]


@admin.post("/templates", status_code=201)
def create_template(data: TemplateIn, db: Session = Depends(get_db), admin_user: User = Depends(MANAGE)):
    if db.query(MarketingTemplate).filter(MarketingTemplate.key == data.key).first():
        raise HTTPException(status_code=409, detail="A template with this key already exists")
    t = MarketingTemplate(**data.model_dump(), updated_by_id=admin_user.id)
    db.add(t)
    db.commit()
    db.refresh(t)
    return _template(t)


@admin.patch("/templates/{template_id}")
def update_template(template_id: uuid.UUID, data: TemplateIn, db: Session = Depends(get_db), admin_user: User = Depends(MANAGE)):
    t = db.query(MarketingTemplate).filter(MarketingTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    for field, value in data.model_dump().items():
        setattr(t, field, value)
    t.version = (t.version or 1) + 1
    t.is_approved = False  # edits require re-approval
    t.updated_by_id = admin_user.id
    db.commit()
    db.refresh(t)
    return _template(t)


@admin.post("/templates/{template_id}/approve")
def approve_template(template_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(APPROVE)):
    t = db.query(MarketingTemplate).filter(MarketingTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    t.is_approved = True
    db.commit()
    return {"approved": True}


@admin.delete("/templates/{template_id}", status_code=204)
def delete_template(template_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(MANAGE)):
    t = db.query(MarketingTemplate).filter(MarketingTemplate.id == template_id).first()
    if t:
        db.delete(t)
        db.commit()


# ------------------------------------------------------------------ campaigns
class CampaignIn(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = None
    channel: str = Field(pattern="^(email|sms)$")
    segment_key: str = "all_customers"
    subject: str | None = None
    body: str = Field(min_length=1)
    template_id: uuid.UUID | None = None
    promotion_id: uuid.UUID | None = None
    scheduled_at: datetime | None = None


@admin.get("/campaigns")
def list_campaigns(status: str | None = None, db: Session = Depends(get_db), _: User = Depends(READ)):
    q = db.query(MarketingCampaign).order_by(MarketingCampaign.created_at.desc())
    if status:
        q = q.filter(MarketingCampaign.status == status)
    return [_campaign(c) for c in q.limit(200).all()]


@admin.post("/campaigns", status_code=201)
def create_campaign(data: CampaignIn, db: Session = Depends(get_db), admin_user: User = Depends(MANAGE)):
    if data.segment_key not in svc.SEGMENTS:
        raise HTTPException(status_code=422, detail="Unknown audience segment")
    if data.template_id:
        tpl = db.query(MarketingTemplate).filter(MarketingTemplate.id == data.template_id).first()
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
    campaign = MarketingCampaign(**data.model_dump(), created_by_id=admin_user.id)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return _campaign(campaign)


@admin.patch("/campaigns/{campaign_id}")
def update_campaign(campaign_id: uuid.UUID, data: CampaignIn, db: Session = Depends(get_db), _: User = Depends(MANAGE)):
    c = db.query(MarketingCampaign).filter(MarketingCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if c.status not in ("draft", "scheduled", "paused"):
        raise HTTPException(status_code=409, detail="Only draft, scheduled or paused campaigns can be edited")
    for field, value in data.model_dump().items():
        setattr(c, field, value)
    if c.status != "draft":
        c.status = "draft"  # edits reset approval
    db.commit()
    db.refresh(c)
    return _campaign(c)


@admin.post("/campaigns/{campaign_id}/approve")
def approve_campaign(campaign_id: uuid.UUID, db: Session = Depends(get_db), admin_user: User = Depends(APPROVE)):
    c = db.query(MarketingCampaign).filter(MarketingCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if c.status not in ("draft", "paused"):
        raise HTTPException(status_code=409, detail="Only draft or paused campaigns can be approved")
    c.status = "approved" if c.scheduled_at else "approved"
    c.approved_by_id = admin_user.id
    c.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(c)
    return _campaign(c)


@admin.post("/campaigns/{campaign_id}/send")
def send_campaign_now(campaign_id: uuid.UUID, db: Session = Depends(get_db), admin_user: User = Depends(APPROVE)):
    """Approve + start sending immediately (queue drained by scheduler tick)."""
    c = db.query(MarketingCampaign).filter(MarketingCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if c.status in ("sending", "sent"):
        raise HTTPException(status_code=409, detail="Campaign is already sending or sent")
    if c.status == "cancelled":
        raise HTTPException(status_code=409, detail="A cancelled campaign cannot be sent")
    c.approved_by_id = admin_user.id
    c.approved_at = datetime.now(timezone.utc)
    c.status = "sending"
    c.started_at = datetime.now(timezone.utc)
    stats = svc.enqueue_campaign(db, c)
    db.commit()
    return {"queued": stats["queued"], "recipients": stats["recipients"]}


@admin.post("/campaigns/{campaign_id}/pause")
def pause_campaign(campaign_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(MANAGE)):
    c = db.query(MarketingCampaign).filter(MarketingCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if c.status in ("approved", "scheduled", "sending"):
        c.status = "paused"
        db.commit()
    return _campaign(c)


@admin.post("/campaigns/{campaign_id}/cancel")
def cancel_campaign(campaign_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(MANAGE)):
    c = db.query(MarketingCampaign).filter(MarketingCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if c.status == "sent":
        raise HTTPException(status_code=409, detail="A sent campaign cannot be cancelled")
    c.status = "cancelled"
    db.commit()
    return _campaign(c)


@admin.post("/campaigns/{campaign_id}/duplicate", status_code=201)
def duplicate_campaign(campaign_id: uuid.UUID, db: Session = Depends(get_db), admin_user: User = Depends(MANAGE)):
    src = db.query(MarketingCampaign).filter(MarketingCampaign.id == campaign_id).first()
    if not src:
        raise HTTPException(status_code=404, detail="Campaign not found")
    c = MarketingCampaign(
        name=f"{src.name} (copy)", description=src.description, channel=src.channel,
        segment_key=src.segment_key, subject=src.subject, body=src.body,
        template_id=src.template_id, promotion_id=src.promotion_id,
        created_by_id=admin_user.id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _campaign(c)


@admin.get("/campaigns/{campaign_id}/messages")
def campaign_messages(
    campaign_id: uuid.UUID,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(READ),
):
    q = db.query(MarketingMessage).filter(MarketingMessage.campaign_id == campaign_id)
    if status:
        q = q.filter(MarketingMessage.status == status)
    total = q.count()
    rows = q.order_by(MarketingMessage.created_at).offset((page - 1) * page_size).limit(page_size).all()
    return {"results": [_message(m) for m in rows], "total": total, "page": page,
            "page_size": page_size, "total_pages": (total + page_size - 1) // page_size}


# ------------------------------------------------------------------ events
@admin.get("/events")
def list_events(year: int | None = None, db: Session = Depends(get_db), _: User = Depends(READ)):
    year = year or datetime.now(timezone.utc).year
    return [_event(e, year) for e in db.query(MarketingEvent).order_by(MarketingEvent.name).all()]


@admin.post("/events/seed")
def seed_events(db: Session = Depends(get_db), _: User = Depends(MANAGE)):
    return {"created": svc.seed_events(db)}


class EventIn(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    rule_type: str = Field(pattern="^(fixed|easter_offset|eid_estimate)$")
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)
    easter_offset: int | None = None
    jurisdiction: str = "tanzania"
    category: str | None = None
    is_estimated: bool = False
    source_url: str | None = None
    lead_days: int = 7
    suggested_email: str | None = None
    suggested_sms: str | None = None
    is_enabled: bool = True


@admin.post("/events", status_code=201)
def create_event(data: EventIn, db: Session = Depends(get_db), _: User = Depends(MANAGE)):
    e = MarketingEvent(**data.model_dump())
    db.add(e)
    db.commit()
    db.refresh(e)
    return _event(e, datetime.now(timezone.utc).year)


@admin.patch("/events/{event_id}")
def update_event(event_id: uuid.UUID, data: EventIn, db: Session = Depends(get_db), _: User = Depends(MANAGE)):
    e = db.query(MarketingEvent).filter(MarketingEvent.id == event_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    for field, value in data.model_dump().items():
        setattr(e, field, value)
    db.commit()
    db.refresh(e)
    return _event(e, datetime.now(timezone.utc).year)


@admin.delete("/events/{event_id}", status_code=204)
def delete_event(event_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(MANAGE)):
    e = db.query(MarketingEvent).filter(MarketingEvent.id == event_id).first()
    if e:
        db.delete(e)
        db.commit()


# ------------------------------------------------------------------ automation
def _automation_row(db: Session) -> MarketingAutomation:
    row = db.query(MarketingAutomation).filter(MarketingAutomation.key == "monthly_engagement").first()
    if row is None:
        row = MarketingAutomation(key="monthly_engagement")
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _auto(a: MarketingAutomation) -> dict:
    return {
        "is_enabled": a.is_enabled, "auto_send": a.auto_send,
        "day_of_month": a.day_of_month, "send_time": a.send_time,
        "timezone": "Africa/Dar_es_Salaam", "channels": a.channels or [],
        "segment_key": a.segment_key,
        "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None,
        "next_run_at": a.next_run_at.isoformat() if a.next_run_at else None,
        "last_campaign_id": str(a.last_campaign_id) if a.last_campaign_id else None,
    }


@admin.get("/automation/monthly")
def get_monthly_automation(db: Session = Depends(get_db), _: User = Depends(READ)):
    return _auto(_automation_row(db))


class AutomationIn(BaseModel):
    is_enabled: bool | None = None
    auto_send: bool | None = None
    day_of_month: int | None = Field(default=None, ge=1, le=28)
    send_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    channels: list[str] | None = None
    segment_key: str | None = None


@admin.patch("/automation/monthly")
def update_monthly_automation(data: AutomationIn, db: Session = Depends(get_db), admin_user: User = Depends(MANAGE)):
    a = _automation_row(db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(a, field, value)
    if data.segment_key and data.segment_key not in svc.SEGMENTS:
        raise HTTPException(status_code=422, detail="Unknown audience segment")
    a.updated_by_id = admin_user.id
    # Recompute next run in EAT.
    now_eat = datetime.now(svc.EAT)
    hh, mm = (a.send_time or "10:00").split(":")
    candidate = now_eat.replace(day=a.day_of_month, hour=int(hh), minute=int(mm), second=0, microsecond=0)
    if candidate <= now_eat:
        month = now_eat.month + 1 or 1
        year = now_eat.year + (1 if now_eat.month == 12 else 0)
        candidate = candidate.replace(year=year, month=month)
    a.next_run_at = candidate.astimezone(timezone.utc)
    db.commit()
    return _auto(a)


# ------------------------------------------------------------------ suppressions
@admin.get("/suppressions")
def list_suppressions(db: Session = Depends(get_db), _: User = Depends(READ)):
    rows = db.query(MarketingPreference).all()
    return [
        {"user_id": str(p.user_id), "email_marketing": p.email_marketing,
         "sms_marketing": p.sms_marketing, "source": p.source,
         "updated_at": p.updated_at.isoformat() if p.updated_at else None}
        for p in rows if not p.email_marketing or not p.sms_marketing
    ]


# ------------------------------------------------------- public unsubscribe
@router.get("/marketing/unsubscribe")
def unsubscribe(token: str = Query(..., min_length=16), channel: str = Query("all"), db: Session = Depends(get_db)):
    pref = db.query(MarketingPreference).filter(MarketingPreference.unsubscribe_token == token).first()
    if not pref:
        raise HTTPException(status_code=404, detail="Invalid unsubscribe link")
    if channel in ("email", "all"):
        pref.email_marketing = False
    if channel in ("sms", "all"):
        pref.sms_marketing = False
    pref.source = "unsubscribe_link"
    db.commit()
    return {"unsubscribed": True, "message": "You have been unsubscribed from Xerin marketing messages."}


router.include_router(admin)
