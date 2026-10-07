from jose import jwt

from api.config import settings
from api.security import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    hash_otp,
    hash_token,
    verify_otp_hash,
)


def test_token_hash_is_deterministic_and_not_plaintext():
    raw = "refresh-token-value"
    digest = hash_token(raw)
    assert digest == hash_token(raw)
    assert digest != raw
    assert len(digest) == 64


def test_otp_hash_verification():
    digest = hash_otp("123456")
    assert verify_otp_hash("123456", digest)
    assert not verify_otp_hash("654321", digest)


def test_access_token_has_access_type_and_claims():
    token = create_access_token({"sub": "00000000-0000-0000-0000-000000000001"})
    payload = jwt.decode(
        token,
        settings.access_token_secret,
        algorithms=[ALGORITHM],
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
    )
    assert payload["type"] == "access"
    assert payload["sub"] == "00000000-0000-0000-0000-000000000001"


def test_refresh_token_has_refresh_type():
    token = create_refresh_token({"sub": "00000000-0000-0000-0000-000000000001"})
    payload = jwt.decode(
        token,
        settings.refresh_token_secret,
        algorithms=[ALGORITHM],
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
    )
    assert payload["type"] == "refresh"
