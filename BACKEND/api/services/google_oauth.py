"""Google ID token verification (OpenID Connect).

Verifies the credential issued by Google Identity Services using Google's
JWKS — no plaintext secrets travel to Xerin, and no per-request calls are
made to Google's tokeninfo endpoint. Audience and issuer are pinned.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient, PyJWTError as JWTError

from api.config import settings

logger = logging.getLogger(__name__)

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

_jwks_client: PyJWKClient | None = None


def _jwks() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True)
    return _jwks_client


@dataclass
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    given_name: str | None
    family_name: str | None
    picture: str | None


def verify_google_id_token(credential: str) -> GoogleIdentity:
    """Verify a Google-issued ID token and return the identity claims.

    Raises ValueError on any verification failure — callers translate that
    into a 401 without exposing internals.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise ValueError("Google sign-in is not configured on this deployment")

    try:
        signing_key = _jwks().get_signing_key_from_jwt(credential).key
        claims = jwt.decode(
            credential,
            signing_key,
            algorithms=["RS256"],
            audience=settings.GOOGLE_CLIENT_ID,
            issuer=list(GOOGLE_ISSUERS),
            options={"require": ["iss", "aud", "exp", "sub", "email"]},
        )
    except JWTError as exc:
        logger.warning("Google ID token verification failed: %s", type(exc).__name__)
        raise ValueError("Invalid Google credential") from exc

    email = (claims.get("email") or "").strip().lower()
    if not email:
        raise ValueError("Google credential is missing an email claim")

    return GoogleIdentity(
        sub=str(claims["sub"]),
        email=email,
        email_verified=bool(claims.get("email_verified")),
        given_name=claims.get("given_name"),
        family_name=claims.get("family_name"),
        picture=claims.get("picture"),
    )
