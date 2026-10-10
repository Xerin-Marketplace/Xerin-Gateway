"""Marketing engine — segments, holiday calendar rules, audience resolution,
and the send pipeline used by the scheduler tick and admin endpoints."""
from __future__ import annotations

import re
import secrets
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.models import (
    Cart,
    CartItem,
    MarketingCampaign,
    MarketingEvent,
    MarketingMessage,
    MarketingPreference,
    MarketingTemplate,
    Order,
    User,
    UserStatus,
)

EAT = timezone(timedelta(hours=3), name="Africa/Dar_es_Salaam")


# ------------------------------------------------------------------ segments
# Segment keys → (label, query-builder). All counts are real SQL.
def _base_users(db: Session):
    return db.query(User).filter(User.status == UserStatus.active)


def _pref(db: Session, user_ids=None):
    """MarketingPreference rows for users (default: opted in when no row)."""
    q = db.query(MarketingPreference)
    if user_ids is not None:
        q = q.filter(MarketingPreference.user_id.in_(user_ids))
    return {p.user_id: p for p in q.all()}


SEGMENTS = {
    "all_customers": "All active customers",
    "email_eligible": "Customers with email marketing enabled",
    "sms_eligible": "Customers with SMS marketing enabled",
    "new_30d": "Registered in the last 30 days",
    "inactive_90d": "No order in the last 90 days",
    "repeat_buyers": "Customers with 2+ completed orders",
    "abandoned_carts": "Customers with items in cart but no recent order",
    "opted_out": "Contacts who opted out of marketing",
}


def _opted_in(prefs: dict, user_id, channel: str) -> bool:
    pref = prefs.get(user_id)
    if pref is None:
        return True  # default = opted in
    return pref.email_marketing if channel == "email" else pref.sms_marketing


def audience(db: Session, segment_key: str, channel: str) -> list[User]:
    """Resolve a segment to eligible users, honoring per-channel consent."""
    now = datetime.now(timezone.utc)
    q = _base_users(db)

    if segment_key == "opted_out":
        prefs = db.query(MarketingPreference).all()
        return [p.user for p in prefs
                if (channel == "email" and not p.email_marketing)
                or (channel == "sms" and not p.sms_marketing)] if prefs else []

    if segment_key == "new_30d":
        q = q.filter(User.created_at >= now - timedelta(days=30))
    elif segment_key == "inactive_90d":
        recent = db.query(Order.user_id).filter(Order.created_at >= now - timedelta(days=90)).subquery()
        q = q.filter(~User.id.in_(recent))
    elif segment_key == "repeat_buyers":
        buyers = (
            db.query(Order.user_id)
            .group_by(Order.user_id)
            .having(func.count(Order.id) >= 2)
            .subquery()
        )
        q = q.filter(User.id.in_(buyers))
    elif segment_key == "abandoned_carts":
        carts = (
            db.query(Cart.user_id)
            .join(CartItem, CartItem.cart_id == Cart.id)
            .subquery()
        )
        recent_orders = db.query(Order.user_id).filter(Order.created_at >= now - timedelta(days=30)).subquery()
        q = q.filter(User.id.in_(carts), ~User.id.in_(recent_orders))

    users = q.all()
    prefs = _pref(db, [u.id for u in users])
    out = []
    for u in users:
        if not _opted_in(prefs, u.id, channel):
            continue
        if channel == "email" and not u.email:
            continue
        if channel == "sms" and not u.phone:
            continue
        out.append(u)
    return out


def segment_counts(db: Session, channel: str = "email") -> dict[str, int]:
    return {key: len(audience(db, key, channel)) for key in SEGMENTS}


# ------------------------------------------------------------ personalization
def render(template_body: str, user: User, extra: dict | None = None) -> str:
    values = {
        "name": (user.first_name or "").strip() or "Customer",
        "first_name": (user.first_name or "").strip() or "Customer",
        "email": user.email or "",
        "phone": user.phone or "",
    }
    if extra:
        values.update(extra)
    def _sub(match):
        return str(values.get(match.group(1).strip(), match.group(0)))
    return re.sub(r"\{\{\s*([a-zA-Z_]+)\s*\}\}", _sub, template_body)


# ------------------------------------------------------------------ holidays
def easter_date(year: int) -> date:
    """Computus — Gregorian Easter Sunday."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def event_date(event: MarketingEvent, year: int) -> date | None:
    if event.rule_type == "fixed" and event.month and event.day:
        return date(year, event.month, event.day)
    if event.rule_type == "easter_offset" and event.easter_offset is not None:
        return easter_date(year) + timedelta(days=event.easter_offset)
    # eid_estimate rows carry the estimated fixed date for the current year —
    # flagged is_estimated so copy can say "subject to confirmation".
    if event.rule_type == "eid_estimate" and event.month and event.day:
        return date(year, event.month, event.day)
    return None


TANZANIA_EVENTS = [
    # (name, rule, month, day, easter_offset, jurisdiction, category, estimated, lead)
    ("New Year's Day", "fixed", 1, 1, None, "tanzania", "public_holiday", False, 7),
    ("Zanzibar Revolution Day", "fixed", 1, 12, None, "zanzibar", "public_holiday", False, 7),
    ("Valentine's Day", "fixed", 2, 14, None, "intl", "observance", False, 10),
    ("International Women's Day", "fixed", 3, 8, None, "intl", "observance", False, 10),
    ("Karume Day", "fixed", 4, 7, None, "tanzania", "public_holiday", False, 7),
    ("Good Friday", "easter_offset", None, None, -2, "tanzania", "public_holiday", False, 10),
    ("Easter Monday", "easter_offset", None, None, 1, "tanzania", "public_holiday", False, 10),
    ("Union Day", "fixed", 4, 26, None, "tanzania", "public_holiday", False, 7),
    ("Labour Day", "fixed", 5, 1, None, "tanzania", "public_holiday", False, 7),
    ("Saba Saba", "fixed", 7, 7, None, "tanzania", "public_holiday", False, 10),
    ("Nane Nane (Farmers' Day)", "fixed", 8, 8, None, "tanzania", "public_holiday", False, 10),
    ("International Youth Day", "fixed", 8, 12, None, "intl", "observance", False, 10),
    ("Mwalimu Nyerere Day", "fixed", 10, 14, None, "tanzania", "public_holiday", False, 7),
    ("World Teachers' Day", "fixed", 10, 5, None, "intl", "observance", False, 10),
    ("Eid al-Fitr (estimated)", "eid_estimate", 3, 30, None, "tanzania", "public_holiday", True, 14),
    ("Eid al-Adha (estimated)", "eid_estimate", 6, 7, None, "tanzania", "public_holiday", True, 14),
    ("Maulid (estimated)", "eid_estimate", 9, 5, None, "tanzania", "public_holiday", True, 10),
    ("Black Friday", "fixed", 11, 28, None, "commercial", "shopping_event", False, 21),
    ("Cyber Monday", "fixed", 12, 1, None, "commercial", "shopping_event", False, 21),
    ("Independence & Republic Day", "fixed", 12, 9, None, "tanzania", "public_holiday", False, 7),
    ("Christmas Day", "fixed", 12, 25, None, "tanzania", "public_holiday", False, 21),
    ("Boxing Day", "fixed", 12, 26, None, "tanzania", "public_holiday", False, 14),
    ("Back-to-School Season", "fixed", 8, 15, None, "commercial", "shopping_event", False, 21),
]

MONTHLY_THEMES = {
    1: ("New-Year Shopping", "Start the year with smart finds — discover products to make everyday life easier."),
    2: ("Customer Appreciation", "Asanteni for shopping with us — here are picks our customers love."),
    3: ("Everyday Essentials", "Great value on everyday essentials, delivered to your door."),
    4: ("Seasonal Picks", "Seasonal shopping made easy — explore what's new this month."),
    5: ("Discover & Save", "Practical tips and products worth discovering this month."),
    6: ("Mid-Year Offers", "Half the year gone — mid-year picks and deals worth a look."),
    7: ("Mid-Year Recommendations", "Products our sellers recommend for the second half of the year."),
    8: ("Back to School", "Back-to-school season — essentials for students and parents."),
    9: ("Everyday Essentials", "Products for home, work and business — all in one place."),
    10: ("Customer Appreciation", "A thank-you to our customers — see what's trending this month."),
    11: ("November Deals", "Our biggest promo season — watch for offers all month long."),
    12: ("Festive Season", "Festive shopping, gift ideas and year-end picks — order early for timely delivery."),
}


def seed_events(db: Session) -> int:
    existing = {e.name for e in db.query(MarketingEvent.name, ).all()}
    existing = {row[0] if isinstance(row, tuple) else row.name for row in existing}
    created = 0
    for name, rule, month, day, offset, jur, cat, est, lead in TANZANIA_EVENTS:
        if name in existing:
            continue
        db.add(MarketingEvent(
            name=name, rule_type=rule, month=month, day=day,
            easter_offset=offset, jurisdiction=jur, category=cat,
            is_estimated=est, lead_days=lead,
        ))
        created += 1
    db.commit()
    return created


# ------------------------------------------------------------------- sending
def _send_email_message(to: str, subject: str, body: str) -> None:
    from api.routers.email import send_email as _send
    _send(to=to, subject=subject, body=body, html=None)


def _send_sms_message(to: str, body: str) -> None:
    from api.routers.sms import send_sms
    send_sms(to=to, message=body)


def enqueue_campaign(db: Session, campaign: MarketingCampaign) -> dict:
    """Resolve the audience into queued MarketingMessage rows."""
    users = audience(db, campaign.segment_key, campaign.channel)
    stats = {"recipients": len(users), "queued": 0, "sent": 0, "failed": 0, "skipped": 0}
    for u in users:
        recipient = u.email if campaign.channel == "email" else u.phone
        if not recipient:
            stats["skipped"] += 1
            continue
        db.add(MarketingMessage(
            campaign_id=campaign.id, user_id=u.id, channel=campaign.channel,
            recipient=recipient, subject=campaign.subject,
            body=render(campaign.body, u),
        ))
        stats["queued"] += 1
    campaign.stats = stats
    return stats


def process_queued_messages(db: Session, limit: int = 50) -> int:
    """Send up to `limit` queued messages. Returns messages attempted."""
    msgs = (
        db.query(MarketingMessage)
        .filter(MarketingMessage.status == "queued")
        .order_by(MarketingMessage.created_at)
        .limit(limit)
        .all()
    )
    for msg in msgs:
        campaign = db.query(MarketingCampaign).filter(MarketingCampaign.id == msg.campaign_id).first()
        if campaign is None or campaign.status in ("cancelled", "paused"):
            msg.status = "skipped"
            continue
        msg.attempts += 1
        try:
            if msg.channel == "email":
                _send_email_message(msg.recipient, msg.subject or "Message from Xerin", msg.body)
            else:
                _send_sms_message(msg.recipient, msg.body)
            msg.status = "sent"
            msg.sent_at = datetime.now(timezone.utc)
            msg.error = None
            if campaign.stats is not None:
                campaign.stats["sent"] = campaign.stats.get("sent", 0) + 1
        except Exception as exc:
            msg.error = f"{type(exc).__name__}: {str(exc)[:300]}"
            msg.status = "failed" if msg.attempts >= 3 else "queued"
            if campaign.stats is not None and msg.status == "failed":
                campaign.stats["failed"] = campaign.stats.get("failed", 0) + 1
        if campaign is not None:
            campaign.stats = dict(campaign.stats or {})
    db.commit()

    # Close out campaigns whose queue is drained.
    busy = db.query(MarketingCampaign).filter(MarketingCampaign.status == "sending").all()
    for campaign in busy:
        pending = (
            db.query(MarketingMessage)
            .filter(MarketingMessage.campaign_id == campaign.id, MarketingMessage.status == "queued")
            .count()
        )
        if pending == 0:
            campaign.status = "sent"
            campaign.sent_at = datetime.now(timezone.utc)
            db.commit()
    return len(msgs)


def tick(db: Session) -> dict:
    """Scheduler entry — promote due campaigns, drain queue, run monthly auto."""
    now = datetime.now(timezone.utc)
    due = (
        db.query(MarketingCampaign)
        .filter(
            MarketingCampaign.status == "approved",
            MarketingCampaign.scheduled_at.isnot(None),
            MarketingCampaign.scheduled_at <= now,
        )
        .all()
    )
    for campaign in due:
        campaign.status = "sending"
        campaign.started_at = now
        enqueue_campaign(db, campaign)
    if due:
        db.commit()

    attempted = process_queued_messages(db)
    return {"promoted": len(due), "attempted": attempted}
