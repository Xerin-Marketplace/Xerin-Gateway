from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from api.config import settings
from api.database import SessionLocal
from api.models import (
    AuditLog, AlertNotification, MigrationEvent, Order, Payment, Product,
    SecurityEvent, Seller, User, WeeklyReport,
)

logger = logging.getLogger(__name__)

_DAYS = {
    "MONDAY": 0, "TUESDAY": 1, "WEDNESDAY": 2, "THURSDAY": 3,
    "FRIDAY": 4, "SATURDAY": 5, "SUNDAY": 6,
}

_loop_started = False
_loop_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def start_monitoring_scheduler() -> None:
    """Spawn the background loop once per process. Safe to call repeatedly."""
    global _loop_started
    with _loop_lock:
        if _loop_started or not settings.MONITORING_ENABLED:
            return
        _loop_started = True
    thread = threading.Thread(
        target=_loop, name="xerin-monitoring", daemon=True,
    )
    thread.start()
    logger.info("Monitoring scheduler started")


def _loop() -> None:
    last_report_check: datetime | None = None
    last_housekeeping: datetime | None = None
    while True:
        try:
            _tick()
        except Exception:
            logger.exception("Monitoring scheduler tick failed")
        now = _now()
        # Weekly report: check at most once per hour.
        if last_report_check is None or now - last_report_check >= timedelta(hours=1):
            try:
                _maybe_send_weekly_report()
            except Exception:
                logger.exception("Weekly report check failed")
            last_report_check = now
        # Housekeeping (retention + schema snapshot): once per 6h.
        if last_housekeeping is None or now - last_housekeeping >= timedelta(hours=6):
            try:
                _housekeeping()
            except Exception:
                logger.exception("Monitoring housekeeping failed")
            last_housekeeping = now
        time.sleep(30)


def _tick() -> None:
    from api.services.email_alerts import process_pending_alerts
    db = SessionLocal()
    try:
        process_pending_alerts(db)
        from api.scripts.cancel_unpaid_orders import cancel_unpaid_orders
        cancel_unpaid_orders(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------- weekly report

def _maybe_send_weekly_report() -> None:
    if not (settings.MONITORING_WEEKLY_REPORT_ENABLED and settings.MONITORING_ALERT_EMAIL):
        return
    target_day = _DAYS.get((settings.MONITORING_WEEKLY_REPORT_DAY or "MONDAY").upper(), 0)
    hh, _, mm = (settings.MONITORING_WEEKLY_REPORT_TIME or "08:00").partition(":")
    now = _now()
    if now.weekday() != target_day or now.hour != int(hh or 8):
        return

    period_end = now
    period_start = now - timedelta(days=7)

    db = SessionLocal()
    try:
        # Idempotent: one report per period.
        exists = (
            db.query(WeeklyReport)
            .filter(
                WeeklyReport.period_start == period_start.replace(minute=int(mm or 0), second=0, microsecond=0),
            )
            .first()
        )
        if exists:
            return
        report = build_weekly_report(db, period_start, period_end)
        db.commit()
    finally:
        db.close()


def build_weekly_report(db: Session, start: datetime, end: datetime) -> WeeklyReport:
    from api.services.email_alerts import send_weekly_report

    stats = _collect_stats(db, start, end)
    subject = f"Xerin Mart — Weekly Report {start.date()} → {end.date()}"
    body = _render_weekly_report(stats, start, end)

    report = WeeklyReport(
        period_start=start, period_end=end, subject=subject,
        body_text=body, stats=stats,
        recipient=settings.MONITORING_ALERT_EMAIL,
        status="pending",
    )
    db.add(report)
    db.flush()
    send_weekly_report(db, report)
    return report


def _collect_stats(db: Session, start: datetime, end: datetime) -> dict:
    def count(model, *filters):
        q = db.query(model).filter(model.created_at.between(start, end))
        for f in filters:
            q = q.filter(f)
        return q.count()

    audits = db.query(AuditLog).filter(AuditLog.created_at.between(start, end)).all()
    by_action: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for row in audits:
        by_action[row.action] = by_action.get(row.action, 0) + 1
        sev = row.severity.value if hasattr(row.severity, "value") else str(row.severity)
        by_severity[sev] = by_severity.get(sev, 0) + 1

    security = db.query(SecurityEvent).filter(SecurityEvent.created_at.between(start, end)).all()
    by_security: dict[str, int] = {}
    unresolved = 0
    for ev in security:
        key = ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type)
        by_security[key] = by_security.get(key, 0) + 1
        if not ev.resolved:
            unresolved += 1

    migrations = (
        db.query(MigrationEvent)
        .filter(MigrationEvent.created_at.between(start, end))
        .order_by(MigrationEvent.created_at.desc())
        .all()
    )

    alerts_sent = count(AlertNotification, AlertNotification.status == "sent")
    alerts_failed = count(AlertNotification, AlertNotification.status == "failed")

    return {
        "users": {
            "new": count(User),
            "total_audit_events": len(audits),
        },
        "sellers": {"new": count(Seller)},
        "orders": {"new": count(Order)},
        "payments": {
            "new": count(Payment),
        },
        "audit": {
            "total": len(audits),
            "by_severity": by_severity,
            "top_actions": sorted(by_action.items(), key=lambda kv: -kv[1])[:12],
        },
        "security": {
            "total": len(security),
            "by_type": by_security,
            "unresolved": unresolved,
        },
        "alerts": {"sent": alerts_sent, "failed": alerts_failed},
        "migrations": [
            {
                "name": m.name or m.revision or "unknown",
                "status": m.status,
                "at": m.created_at.isoformat(timespec="seconds") if m.created_at else None,
                "error": (m.error_summary or "")[:160] or None,
            }
            for m in migrations[:25]
        ],
    }


def _render_weekly_report(stats: dict, start: datetime, end: datetime) -> str:
    line = "=" * 60

    def section(title: str) -> str:
        return f"\n{title}\n{'-' * len(title)}"

    parts = [
        "XERIN MART — WEEKLY OPERATIONS REPORT",
        line,
        f"Period      : {start.date()} → {end.date()}",
        f"Generated   : {_now().isoformat(timespec='seconds')}",
        f"Environment : {settings.APP_ENV}",
    ]

    parts.append(section("SYSTEM OVERVIEW"))
    parts.append(f"  Audit events          : {stats['audit']['total']}")
    parts.append(f"  Severity breakdown    : {json.dumps(stats['audit']['by_severity'])}")
    parts.append(f"  Alert emails sent     : {stats['alerts']['sent']}")
    parts.append(f"  Alert emails failed   : {stats['alerts']['failed']}")

    parts.append(section("USERS"))
    parts.append(f"  New users             : {stats['users']['new']}")

    parts.append(section("SELLERS"))
    parts.append(f"  New sellers           : {stats['sellers']['new']}")

    parts.append(section("ORDERS & PAYMENTS"))
    parts.append(f"  New orders            : {stats['orders']['new']}")
    parts.append(f"  Payment records       : {stats['payments']['new']}")

    parts.append(section("SECURITY"))
    parts.append(f"  Security events       : {stats['security']['total']}")
    parts.append(f"  Unresolved            : {stats['security']['unresolved']}")
    for kind, n in stats["security"]["by_type"].items():
        parts.append(f"    {kind:<34} {n}")

    parts.append(section("DATABASE MIGRATIONS"))
    if stats["migrations"]:
        for m in stats["migrations"]:
            flag = "  " if m["status"] == "succeeded" else "! "
            parts.append(f"  {flag}{m['status']:<12} {m['name']} @ {m['at']}")
            if m.get("error"):
                parts.append(f"      error: {m['error']}")
    else:
        parts.append("  No migrations recorded this week.")

    parts.append(section("TOP ACTIVITY"))
    for action, n in stats["audit"]["top_actions"]:
        parts.append(f"    {n:>5}  {action}")

    parts.append(f"\n{line}\nAutomated report — Xerin Mart monitoring")
    return "\n".join(parts)


# ---------------------------------------------------------------- housekeeping

def _housekeeping() -> None:
    db = SessionLocal()
    try:
        _enforce_retention(db)
        _schema_snapshot(db)
        db.commit()
    finally:
        db.close()


def _enforce_retention(db: Session) -> None:
    days = settings.AUDIT_LOG_RETENTION_DAYS
    if not days or days <= 0:
        return
    cutoff = _now() - timedelta(days=days)
    # Keep unresolved/critical security events regardless of age.
    deleted = (
        db.query(AuditLog)
        .filter(AuditLog.created_at < cutoff, AuditLog.severity != "critical")
        .delete(synchronize_session=False)
    )
    if deleted:
        db.add(AuditLog(
            request_id=f"ret_{_now().strftime('%Y%m%d%H%M%S')}",
            action="maintenance.audit_retention",
            severity="notice",
            event_metadata={"deleted_rows": deleted, "cutoff": cutoff.isoformat()},
        ))


_SCHEMA_SNAPSHOT_KEY = "monitoring.schema_hash"


def _schema_snapshot(db: Session) -> None:
    """Lightweight drift detection: hash of information_schema catalog."""
    rows = db.execute(text(
        "SELECT table_name, column_name, data_type "
        "FROM information_schema.columns "
        "WHERE table_schema = 'public' ORDER BY 1, 2"
    )).all()
    digest = hashlib.sha256(
        "\n".join(f"{r[0]}.{r[1]}:{r[2]}" for r in rows).encode()
    ).hexdigest()

    from api.models import SystemSetting
    setting = db.query(SystemSetting).filter(
        SystemSetting.key == _SCHEMA_SNAPSHOT_KEY
    ).first()
    if setting is None:
        db.add(SystemSetting(key=_SCHEMA_SNAPSHOT_KEY, value=digest, is_public=False))
        return
    if setting.value != digest:
        db.add(SecurityEvent(
            request_id=f"schema_{_now().strftime('%Y%m%d%H%M%S')}",
            event_type="suspicious_request",
            severity="warning",
            description="Database schema drift detected — catalog hash changed "
                        "outside a recorded migration event",
            event_metadata={"old_hash": setting.value, "new_hash": digest},
        ))
        setting.value = digest
