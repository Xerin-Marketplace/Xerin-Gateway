from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from api.config import settings
import random

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str):
    return pwd_context.verify(password, hashed)


def create_access_token(data: dict):
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    data.update({"exp": expire, "type": "access"})
    return jwt.encode(data, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict):
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    data.update({"exp": expire, "type": "refresh"})
    return jwt.encode(data, settings.SECRET_KEY, algorithm=ALGORITHM)


def generate_otp():
    return str(random.randint(100000, 999999))