#!/usr/bin/env python3
"""Migration runner with audit monitoring.

Wraps `alembic upgrade head` and records the run in migration_events —
started / succeeded / failed — so production schema changes are
auditable and alertable.

Usage:
    python scripts/run_migrations.py              # upgrade head
    python scripts/run_migrations.py downgrade -1 # recorded rollback
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.config import settings  # noqa: E402
from api.database import SessionLocal  # noqa: E402
from api.models import MigrationEvent  # noqa: E402
from api.services.monitoring import queue_email_alert, _alert_body  # noqa: E402


def record(status: str, *, revision=None, name=None, error=None, duration_ms=None):
    db = SessionLocal()
    try:
        event = MigrationEvent(
            revision=revision, name=name, status=status,
            environment=settings.APP_ENV,
            app_version=settings.APP_VERSION,
            error_summary=(error or "")[:4000] or None,
            duration_ms=duration_ms,
        )
        db.add(event)
        if status == "failed" and settings.MONITORING_ALERT_EMAIL:
            queue_email_alert(
                db,
                dedup_key=f"migration.failed:{revision or name or 'unknown'}",
                subject=f"[Xerin CRITICAL] Database migration failed — {name or revision}",
                body_text=_alert_body(
                    severity="critical",
                    title="DATABASE CHANGE — MIGRATION FAILED",
                    details={
                        "Migration": name or revision or "unknown",
                        "Status": "FAILED",
                        "Environment": settings.APP_ENV,
                        "App version": settings.APP_VERSION or "-",
                        "Error": (error or "")[:600],
                    },
                ),
                severity="critical",
                event_type="migration.failed",
            )
        db.commit()
        return event
    finally:
        db.close()


def main() -> int:
    args = sys.argv[1:] or ["upgrade", "head"]
    started = time.time()
    record("started", name=" ".join(args))
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=os.path.join(os.path.dirname(__file__), ".."),
    )
    duration_ms = int((time.time() - started) * 1000)
    ok = proc.returncode == 0
    record(
        "succeeded" if ok else "failed",
        name=" ".join(args),
        error=None if ok else f"alembic exited with code {proc.returncode}",
        duration_ms=duration_ms,
    )
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
