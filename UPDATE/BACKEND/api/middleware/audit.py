from __future__ import annotations

import logging
from uuid import UUID, uuid4

from fastapi import Request
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from api.config import settings
from api.database import SessionLocal
from api.enums import AuditSeverity, SecurityEventType
from api.security import ALGORITHM
from api.services.audit_service import create_audit_log, create_security_event

logger = logging.getLogger(__name__)

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SKIPPED_PATHS = {"/health/live", "/health/ready", "/docs", "/redoc", "/openapi.json"}


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()[:64]
    return request.client.host[:64] if request.client else None


def _actor_id(request: Request) -> UUID | None:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    token = header.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(
            token,
            settings.access_token_secret,
            algorithms=[ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
        )
        return UUID(str(payload.get("sub")))
    except (JWTError, TypeError, ValueError):
        return None


def _action(method: str, path: str) -> str:
    cleaned = path.strip("/").replace("/", ".") or "root"
    return f"http.{method.lower()}.{cleaned}"[:120]


def _resource(path: str) -> tuple[str | None, str | None]:
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 3 and parts[0] == "api" and parts[1].startswith("v"):
        resource_type = parts[2][:120]
        resource_id = parts[3][:180] if len(parts) > 3 else None
        return resource_type, resource_id
    return (parts[0][:120], parts[1][:180] if len(parts) > 1 else None) if parts else (None, None)


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        except Exception:
            self._persist(request, request_id, 500)
            raise

        response.headers["X-Request-ID"] = request_id
        self._persist(request, request_id, response.status_code)
        return response

    def _persist(self, request: Request, request_id: str, response_status: int) -> None:
        path = request.url.path
        method = request.method.upper()
        if path in SKIPPED_PATHS or method not in MUTATING_METHODS:
            return

        actor_user_id = _actor_id(request)
        resource_type, resource_id = _resource(path)
        severity = AuditSeverity.info
        if response_status >= 500:
            severity = AuditSeverity.critical
        elif response_status in {401, 403}:
            severity = AuditSeverity.warning

        db = SessionLocal()
        try:
            create_audit_log(
                db,
                request_id=request_id,
                actor_user_id=actor_user_id,
                action=_action(method, path),
                resource_type=resource_type,
                resource_id=resource_id,
                http_method=method,
                request_path=path,
                response_status=response_status,
                event_metadata={"query_keys": sorted(request.query_params.keys())},
                ip_address=_client_ip(request),
                user_agent=request.headers.get("user-agent", "")[:2000] or None,
                severity=severity,
            )

            if response_status in {401, 403}:
                event_type = (
                    SecurityEventType.authentication_failed
                    if response_status == 401
                    else SecurityEventType.authorization_denied
                )
                create_security_event(
                    db,
                    request_id=request_id,
                    actor_user_id=actor_user_id,
                    event_type=event_type,
                    description=f"Request returned HTTP {response_status}",
                    severity=AuditSeverity.warning,
                    request_path=path,
                    http_method=method,
                    response_status=response_status,
                    ip_address=_client_ip(request),
                    user_agent=request.headers.get("user-agent", "")[:2000] or None,
                )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Unable to persist audit record for request %s", request_id)
        finally:
            db.close()
