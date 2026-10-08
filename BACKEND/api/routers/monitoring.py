from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import AuditSeverity, PermissionCode
from api.models import (
    AlertNotification, AuditLog, MigrationEvent, SecurityEvent,
    User, WeeklyReport,
)
from api.permissions import require_permission
from api.config import settings
from api.services.monitoring import alert_recipients

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


def _log_dict(row: AuditLog) -> dict:
    return {
        "id": str(row.id),
        "action": row.action,
        "severity": row.severity.value if hasattr(row.severity, "value") else row.severity,
        "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
        "resource_type": row.resource_type,
        "resource_id": row.resource_id,
        "http_method": row.http_method,
        "request_path": row.request_path,
        "response_status": row.response_status,
        "ip_address": row.ip_address,
        "request_id": row.request_id,
        "metadata": row.event_metadata,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/overview")
def monitoring_overview(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.monitoring_read.value)),
):
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    def audit_count(*filters):
        return db.query(func.count(AuditLog.id)).filter(*filters).scalar() or 0

    critical_24h = audit_count(
        AuditLog.severity == AuditSeverity.critical,
        AuditLog.created_at >= day_ago,
    )
    warnings_24h = audit_count(
        AuditLog.severity == AuditSeverity.warning,
        AuditLog.created_at >= day_ago,
    )
    security_open = (
        db.query(func.count(SecurityEvent.id))
        .filter(SecurityEvent.resolved.is_(False))
        .scalar() or 0
    )
    pending_alerts = (
        db.query(func.count(AlertNotification.id))
        .filter(AlertNotification.status == "pending")
        .scalar() or 0
    )
    failed_alerts = (
        db.query(func.count(AlertNotification.id))
        .filter(AlertNotification.status == "failed",
                AlertNotification.created_at >= week_ago)
        .scalar() or 0
    )
    last_migration = (
        db.query(MigrationEvent)
        .order_by(MigrationEvent.created_at.desc())
        .first()
    )
    last_report = (
        db.query(WeeklyReport)
        .order_by(WeeklyReport.created_at.desc())
        .first()
    )

    return {
        "enabled": settings.MONITORING_ENABLED,
        "alert_recipients": alert_recipients(),
        "weekly_report": {
            "enabled": settings.MONITORING_WEEKLY_REPORT_ENABLED,
            "day": settings.MONITORING_WEEKLY_REPORT_DAY,
            "time": settings.MONITORING_WEEKLY_REPORT_TIME,
            "last_sent": last_report.sent_at.isoformat() if last_report and last_report.sent_at else None,
            "last_status": last_report.status if last_report else None,
        },
        "last_24h": {
            "audit_events": audit_count(AuditLog.created_at >= day_ago),
            "critical": critical_24h,
            "warnings": warnings_24h,
            "security_events": db.query(func.count(SecurityEvent.id))
                .filter(SecurityEvent.created_at >= day_ago).scalar() or 0,
            "server_errors": audit_count(
                AuditLog.response_status >= 500,
                AuditLog.created_at >= day_ago,
            ),
        },
        "open_security_events": security_open,
        "pending_alerts": pending_alerts,
        "failed_alerts_7d": failed_alerts,
        "last_migration": {
            "name": last_migration.name or last_migration.revision,
            "status": last_migration.status,
            "at": last_migration.created_at.isoformat(),
        } if last_migration else None,
    }


@router.get("/events")
def list_monitoring_events(
    severity: AuditSeverity | None = None,
    action_prefix: str | None = None,
    actor_user_id: str | None = None,
    hours: int = Query(24, ge=1, le=24 * 30),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.monitoring_read.value)),
):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = db.query(AuditLog).filter(AuditLog.created_at >= cutoff)
    if severity:
        query = query.filter(AuditLog.severity == severity)
    if action_prefix:
        query = query.filter(AuditLog.action.startswith(action_prefix))
    if actor_user_id:
        query = query.filter(AuditLog.actor_user_id == actor_user_id)
    rows = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    return [_log_dict(r) for r in rows]


@router.get("/security-events")
def list_monitoring_security_events(
    severity: AuditSeverity | None = None,
    resolved: bool | None = None,
    hours: int = Query(168, ge=1, le=24 * 90),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.monitoring_read.value)),
):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = db.query(SecurityEvent).filter(SecurityEvent.created_at >= cutoff)
    if severity:
        query = query.filter(SecurityEvent.severity == severity)
    if resolved is not None:
        query = query.filter(SecurityEvent.resolved.is_(resolved))
    rows = query.order_by(SecurityEvent.created_at.desc()).limit(limit).all()
    return [
        {
            "id": str(r.id),
            "event_type": r.event_type.value if hasattr(r.event_type, "value") else r.event_type,
            "severity": r.severity.value if hasattr(r.severity, "value") else r.severity,
            "description": r.description,
            "request_path": r.request_path,
            "http_method": r.http_method,
            "ip_address": r.ip_address,
            "resolved": r.resolved,
            "request_id": r.request_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/alerts")
def list_alert_notifications(
    status: str | None = Query(None, pattern="^(pending|sent|failed|cancelled)$"),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.monitoring_read.value)),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = db.query(AlertNotification).filter(AlertNotification.created_at >= cutoff)
    if status:
        query = query.filter(AlertNotification.status == status)
    rows = query.order_by(AlertNotification.created_at.desc()).limit(limit).all()
    return [
        {
            "id": str(r.id),
            "subject": r.subject,
            "severity": r.severity,
            "event_type": r.event_type,
            "status": r.status,
            "attempts": r.attempts,
            "aggregate_count": r.aggregate_count,
            "last_error": r.last_error,
            "sent_at": r.sent_at.isoformat() if r.sent_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/migrations")
def list_migration_events(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.monitoring_read.value)),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(MigrationEvent)
        .filter(MigrationEvent.created_at >= cutoff)
        .order_by(MigrationEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(r.id),
            "revision": r.revision,
            "name": r.name,
            "status": r.status,
            "environment": r.environment,
            "app_version": r.app_version,
            "error_summary": r.error_summary,
            "duration_ms": r.duration_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/reports")
def list_weekly_reports(
    limit: int = Query(26, ge=1, le=104),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.monitoring_read.value)),
):
    rows = (
        db.query(WeeklyReport)
        .order_by(WeeklyReport.period_start.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(r.id),
            "subject": r.subject,
            "period_start": r.period_start.isoformat() if r.period_start else None,
            "period_end": r.period_end.isoformat() if r.period_end else None,
            "status": r.status,
            "sent_at": r.sent_at.isoformat() if r.sent_at else None,
            "stats": r.stats,
        }
        for r in rows
    ]


# ------------------------------------------------------------------ jobs

@router.get("/jobs")
def list_background_jobs(
    _: User = Depends(require_permission(PermissionCode.monitoring_read.value)),
):
    from api.services import scheduler
    return scheduler.job_statuses()


@router.post("/jobs/{job_id}/retry")
def retry_background_job(
    job_id: str,
    _: User = Depends(require_permission(PermissionCode.monitoring_read.value)),
):
    from api.services import scheduler
    row = scheduler.trigger_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown job")
    return row


@router.post("/jobs/{job_id}/cancel")
def cancel_background_job(
    job_id: str,
    _: User = Depends(require_permission(PermissionCode.monitoring_read.value)),
):
    from api.services import scheduler
    row = scheduler.pause_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown job")
    return row


# ------------------------------------------------------------------ jobs

@router.get("/jobs")
def list_background_jobs(
    _: User = Depends(require_permission(PermissionCode.monitoring_read.value)),
):
    from api.services import scheduler
    return scheduler.job_statuses()


@router.post("/jobs/{job_id}/retry")
def retry_background_job(
    job_id: str,
    _: User = Depends(require_permission(PermissionCode.monitoring_read.value)),
):
    from api.services import scheduler
    row = scheduler.trigger_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown job")
    return row


@router.post("/jobs/{job_id}/cancel")
def cancel_background_job(
    job_id: str,
    _: User = Depends(require_permission(PermissionCode.monitoring_read.value)),
):
    from api.services import scheduler
    row = scheduler.pause_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown job")
    return row
