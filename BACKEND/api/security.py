from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import bcrypt
from jose import jwt

from api.config import settings


ALGORITHM = settings.JWT_ALGORITHM


def _password_bytes(password: str) -> bytes:
    if not isinstance(password, str):
        raise TypeError("Password must be a string")

    encoded = password.encode("utf-8")
    if len(encoded) > 72:
        raise ValueError("Password is too long for bcrypt; maximum is 72 UTF-8 bytes")
    return encoded


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_password_bytes(password), hashed.encode("utf-8"))
    except (TypeError, ValueError):
        return False


def _create_token(
    data: dict[str, Any],
    *,
    token_type: str,
    expires_delta: timedelta,
    secret: str,
) -> str:
    now = datetime.now(timezone.utc)
    payload = dict(data)
    payload.update(
        {
            "iat": now,
            "exp": now + expires_delta,
            "jti": str(uuid4()),
            "type": token_type,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }
    )
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def create_access_token(data: dict[str, Any]) -> str:
    return _create_token(
        data,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        secret=settings.access_token_secret,
    )


def create_refresh_token(data: dict[str, Any]) -> str:
    return _create_token(
        data,
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        # Keep SECRET_KEY compatibility until auth.py refresh decoding is updated.
        secret=settings.refresh_token_secret,
    )


def generate_otp() -> str:
    """Generate a cryptographically secure six-digit OTP."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_token(token: str) -> str:
    """Create a one-way SHA-256 digest for refresh tokens and similar secrets."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_compare(value_a: str, value_b: str) -> bool:
    return secrets.compare_digest(value_a, value_b)
