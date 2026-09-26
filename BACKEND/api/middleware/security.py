from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from api.config import settings

AUTH_BUCKET_LIMIT = 40
AUTH_BUCKET_WINDOW_SECONDS = 5 * 60

_buckets: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    """Mirror the auth-router logic: only trust X-Forwarded-For when the
    deployment is explicitly behind a trusted proxy."""
    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    """Coarse brute-force shield covering every write under /auth/ —
    complements the stricter per-endpoint limits inside the router.
    In-memory sliding window (matches the existing fallback limiter);
    Redis-backed per-endpoint limits still apply on top of this."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        auth_prefix = f"{settings.API_PREFIX}/auth"
        if request.method == "POST" and request.url.path.startswith(auth_prefix):
            ip = _client_ip(request)
            now = time.time()
            with _lock:
                bucket = _buckets[ip]
                while bucket and bucket[0] < now - AUTH_BUCKET_WINDOW_SECONDS:
                    bucket.popleft()
                if len(bucket) >= AUTH_BUCKET_LIMIT:
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Too many authentication attempts. Try again later."},
                        headers={"Retry-After": str(AUTH_BUCKET_WINDOW_SECONDS)},
                    )
                bucket.append(now)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Conservative HTTP hardening headers on every response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        # HSTS only makes sense once the API is actually served over HTTPS.
        if settings.is_production:
            headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        # Auth/cache-sensitive responses should never be stored by caches.
        if request.url.path.startswith(f"{settings.API_PREFIX}/auth"):
            headers.setdefault("Cache-Control", "no-store")
            headers.setdefault("Pragma", "no-cache")
        return response
