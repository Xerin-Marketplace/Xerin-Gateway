from __future__ import annotations

from datetime import datetime, timezone
from typing import Generator
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session

from api.config import settings
from api.database import SessionLocal
from api.models import Session as UserSession, User, UserStatus
from api.security import ALGORITHM


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_PREFIX}/auth/login" if settings.API_PREFIX else "/auth/login"
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _credentials_exception(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(
            token,
            settings.access_token_secret,
            algorithms=[ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
        )

        subject = payload.get("sub")
        token_type = payload.get("type")
        session_id = payload.get("sid")

        if not subject or token_type != "access":
            raise _credentials_exception("Invalid access token")

        try:
            user_id = UUID(str(subject))
        except (TypeError, ValueError):
            raise _credentials_exception("Invalid token subject")

    except ExpiredSignatureError:
        raise _credentials_exception("Access token has expired")
    except JWTError:
        raise _credentials_exception("Invalid access token")

    # New access tokens are bound to a DB session. Deleting/revoking the
    # session therefore invalidates the access token immediately. Legacy
    # tokens without `sid` remain accepted until their normal JWT expiry.
    if session_id:
        try:
            session_uuid = UUID(str(session_id))
        except (TypeError, ValueError):
            raise _credentials_exception("Invalid session")

        active_session = (
            db.query(UserSession)
            .filter(
                UserSession.id == session_uuid,
                UserSession.user_id == user_id,
                UserSession.expires_at > datetime.now(timezone.utc),
            )
            .first()
        )
        if active_session is None:
            raise _credentials_exception("Session has been revoked or expired")
        active_session.last_seen_at = datetime.now(timezone.utc)
        db.commit()

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise _credentials_exception("User not found")

    if user.status == UserStatus.suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended",
        )

    if user.status == UserStatus.inactive:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    if user.status == UserStatus.pending_verification or not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account verification is required",
        )

    return user
