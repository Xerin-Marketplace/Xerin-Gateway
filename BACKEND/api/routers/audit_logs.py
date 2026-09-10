from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import AuditSeverity, PermissionCode, SecurityEventType
from api.models import AuditLog, SecurityEvent, User
from api.permissions import require_permission
from api.schemas import AuditLogResponse, SecurityEventResolve, SecurityEventResponse
from api.services.audit_service import resolve_security_event

router = APIRouter(prefix="/audit-logs", tags=["Audit and Security"])


@router.get("", response_model=list[AuditLogResponse])
def list_audit_logs(
    actor_user_id: UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    severity: AuditSeverity | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.audit_logs_read.value)),
):
    query = db.query(AuditLog)
    if actor_user_id is not None:
        query = query.filter(AuditLog.actor_user_id == actor_user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if severity is not None:
        query = query.filter(AuditLog.severity == severity)
    if start_at is not None:
        query = query.filter(AuditLog.created_at >= start_at)
    if end_at is not None:
        query = query.filter(AuditLog.created_at < end_at)
    return query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/security/events", response_model=list[SecurityEventResponse])
def list_security_events(
    event_type: SecurityEventType | None = None,
    severity: AuditSeverity | None = None,
    resolved: bool | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.security_events_read.value)),
):
    query = db.query(SecurityEvent)
    if event_type is not None:
        query = query.filter(SecurityEvent.event_type == event_type)
    if severity is not None:
        query = query.filter(SecurityEvent.severity == severity)
    if resolved is not None:
        query = query.filter(SecurityEvent.resolved.is_(resolved))
    if start_at is not None:
        query = query.filter(SecurityEvent.created_at >= start_at)
    if end_at is not None:
        query = query.filter(SecurityEvent.created_at < end_at)
    return query.order_by(SecurityEvent.created_at.desc()).offset(offset).limit(limit).all()


@router.patch("/security/events/{event_id}/resolve", response_model=SecurityEventResponse)
def resolve_event(
    event_id: UUID,
    payload: SecurityEventResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.security_events_read.value)),
):
    event = db.query(SecurityEvent).filter(SecurityEvent.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Security event not found")
    if not event.resolved:
        resolve_security_event(db, event, resolved_by_id=current_user.id, note=payload.note)
        db.commit()
        db.refresh(event)
    return event


@router.get("/{audit_id}", response_model=AuditLogResponse)
def get_audit_log(
    audit_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.audit_logs_read.value)),
):
    record = db.query(AuditLog).filter(AuditLog.id == audit_id).first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit log not found")
    return record


