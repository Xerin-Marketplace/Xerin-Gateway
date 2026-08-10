from __future__ import annotations

from typing import Generator
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session

from api.config import settings
from api.database import SessionLocal
from api.models import User, UserStatus
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
