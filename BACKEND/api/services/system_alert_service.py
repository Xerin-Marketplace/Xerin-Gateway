from __future__ import annotations
from sqlalchemy.orm import Session
from api.models import SystemAlert


def create_alert(db: Session, *, alert_type: str, title: str, message: str, severity: str = "warning", source: str | None = None, metadata: dict | None = None):
    alert = SystemAlert(alert_type=alert_type, title=title, message=message, severity=severity, source=source, metadata_json=metadata or {})
    db.add(alert); db.commit(); db.refresh(alert); return alert
