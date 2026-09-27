from __future__ import annotations

import logging
import re
import time
import urllib.parse
from collections import defaultdict, deque
from threading import Lock
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from api.config import settings
from api.database import SessionLocal
from api.enums import AuditSeverity, SecurityEventType
from api.services.audit_service import create_security_event

logger = logging.getLogger(__name__)

# Conservative, high-signal attack signatures. These run against the
# *decoded* path + query string only — request bodies are left to the
# routers' validators (avoiding the cost/fragility of consuming streams).
_SQLI_PATTERN = re.compile(
    r"('|%27)\s*(or|and)\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+['\"]?"
    r"|union\s+(all\s+)?select\b"
    r"|\b(or|and)\s+1\s*=\s*1\b"
    r"|\bselect\b.+\bfrom\b.+\binformation_schema\b"
    r"|\b(drop|truncate|alter)\s+table\b"
    r"|;\s*(drop|insert|update|delete|truncate)\b"
    r"|xp_cmdshell|exec\s*\(|--\s*$|/\*.*\*/",
    re.IGNORECASE,
)
_XSS_PATTERN = re.compile(
    r"<\s*script|javascript:|on(error|load|click)\s*=|data:text/html",
    re.IGNORECASE,
)
_TRAVERSAL_PATTERN = re.compile(
    r"\.\./|\.\.\\|%2e%2e|%252e|/etc/passwd|/proc/|win\.ini",
    re.IGNORECASE,
)
_COMMAND_PATTERN = re.compile(
    r";\s*(cat|ls|id|whoami|uname|wget|curl)\b"
    r"|\|\s*(cat|ls|id|whoami|wget|curl)\b"
    r"|`[^`]*`|\$\{",
    re.IGNORECASE,
)

SKIPPED_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/health/", "/uploads/")


def _classify(payload: str) -> tuple[SecurityEventType, str] | None:
    if _SQLI_PATTERN.search(payload):
        return SecurityEventType.sql_injection_attempt, "sql_injection"
    if _TRAVERSAL_PATTERN.search(payload):
        return SecurityEventType.path_traversal_attempt, "path_traversal"
    if _XSS_PATTERN.search(payload):
        return SecurityEventType.xss_attempt, "xss"
    if _COMMAND_PATTERN.search(payload):
        return SecurityEventType.command_injection_attempt, "command_injection"
    return None


def _client_ip(request: Request) -> str:
    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


class IntrusionDetectionMiddleware(BaseHTTPMiddleware):
    """Blocks obvious injection/traversal payloads before routers see them
    and records a deduplicated security event per request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.MONITORING_ENABLED:
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(p) for p in SKIPPED_PREFIXES):
            return await call_next(request)

        # Decode once so %27, %3C etc are evaluated as characters.
        payload = urllib.parse.unquote_plus(f"{path}?{request.url.query}")
        verdict = _classify(payload)
        if verdict is None:
            return await call_next(request)

        event_type, kind = verdict
        request_id = f"req_{uuid4().hex[:20]}"
        ip = _client_ip(request)

        try:
            db = SessionLocal()
            try:
                create_security_event(
                    db,
                    request_id=request_id,
                    event_type=event_type,
                    description=f"{kind} signature blocked on {request.method} {path}",
                    severity=AuditSeverity.critical,
                    request_path=path[:500],
                    http_method=request.method,
                    response_status=400,
                    ip_address=ip,
                    user_agent=request.headers.get("user-agent", "")[:2000] or None,
                    event_metadata={"matched_pattern_kind": kind},
                )
                db.commit()
            finally:
                db.close()
        except Exception:
            logger.exception("Failed to persist intrusion event")

        # Queue an email alert in a separate session so a slow alert path
        # never delays the blocked response.
        try:
            _queue_intrusion_alert(event_type, path, request.method, request_id, ip)
        except Exception:
            logger.exception("Failed to queue intrusion alert")

        return JSONResponse(
            status_code=400,
            content={"detail": "Bad request", "request_id": request_id},
        )


def _queue_intrusion_alert(event_type, path: str, method: str, request_id: str, ip: str) -> None:
    from api.services.monitoring import queue_email_alert, _alert_body
    from api.enums import AuditSeverity

    db = SessionLocal()
    try:
        queue_email_alert(
            db,
            dedup_key=f"security.{event_type.value}:{path}",
            subject=f"[Xerin SECURITY CRITICAL] {event_type.value}",
            body_text=_alert_body(
                severity=AuditSeverity.critical,
                title=f"SECURITY ALERT — {event_type.value.replace('_', ' ').upper()}",
                details={
                    "Event": event_type.value,
                    "Endpoint": path,
                    "Method": method,
                    "Request ID": request_id,
                    "IP": ip,
                    "Action": "BLOCKED",
                },
            ),
            severity=AuditSeverity.critical,
            event_type=f"security.{event_type.value}",
        )
        db.commit()
    finally:
        db.close()
