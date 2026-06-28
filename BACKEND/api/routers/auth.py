from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from jose import jwt, JWTError
import logging

from api.database import SessionLocal
from api.deps import get_db, get_current_user
from api.models import User, Session as UserSession, OTPRequest, UserStatus
from api.schemas import *
from api.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    generate_otp,
    ALGORITHM,
)
from api.config import settings
# from api.utils import send_email, send_sms
from api.routers.email import send_email as _send_email
from api.routers.sms import send_sms as _send_sms

def send_email(to: str, subject: str, body: str, html: str | None = None) -> None:
    return _send_email(to=to, subject=subject, body=body, html=html)

def send_sms(to: str, message: str) -> None:
    return _send_sms(to=to, message=message)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    # normalize inputs
    email = data.email.strip().lower()
    phone = data.phone.strip()

    existing_user = (
        db.query(User)
        .filter((User.email == email) | (User.phone == phone))
        .first()
    )

    if existing_user:
        raise HTTPException(status_code=400, detail="Email or phone already exists")

    user = User(
        first_name=data.first_name,
        last_name=data.last_name,
        email=email,
        phone=phone,
        password_hash=hash_password(data.password),
        status=UserStatus.pending_verification,
        is_verified=False,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # generate OTP and persist
    otp = generate_otp()
    otp_request = OTPRequest(
        user_id=user.id,
        phone=phone,
        otp_code=otp,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        verified=False,
    )

    db.add(otp_request)
    db.commit()

    # send OTP via email and SMS (best-effort; failures do not block registration)
    try:
        send_email(
            to=email,
            subject="Verify your account",
            body=f"Your verification code is: {otp}",
        )
    except Exception as e:
        logger.exception("send_email failed for %s: %s", email, e)

    try:
        send_sms(
            to=phone,
            message=f"Use this OTP for verification in Exerim market Place and Your verification code is: {otp}",
        )
    except Exception as e:
        logger.exception("send_sms failed for %s: %s", phone, e)

    # In development you may want to return dev_otp; production should not expose it.
    return user


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.status == UserStatus.suspended:
        raise HTTPException(status_code=403, detail="Account suspended")

    # Enforce verification before allowing login
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Account not verified")

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    session = UserSession(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )

    user.last_login_at = datetime.now(timezone.utc)

    db.add(session)
    db.commit()

    return {"access_token": access_token, "refresh_token": refresh_token}


@router.post("/logout")
def logout(
    data: RefreshRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == current_user.id,
            UserSession.refresh_token == data.refresh_token,
        )
        .first()
    )

    if session:
        db.delete(session)
        db.commit()

    return {"message": "Logged out successfully"}


@router.post("/refresh-token", response_model=TokenResponse)
def refresh_token(data: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(
            data.refresh_token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        user_id = payload.get("sub")
        token_type = payload.get("type")

        if token_type != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    session = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == user_id,
            UserSession.refresh_token == data.refresh_token,
        )
        .first()
    )

    if not session:
        raise HTTPException(status_code=401, detail="Refresh token not found")

    access_token = create_access_token({"sub": str(user_id)})
    new_refresh_token = create_refresh_token({"sub": str(user_id)})

    session.refresh_token = new_refresh_token
    session.expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    db.commit()

    return {"access_token": access_token, "refresh_token": new_refresh_token}


@router.post("/send-otp")
def send_otp(data: SendOTPRequest, db: Session = Depends(get_db)):
    otp = generate_otp()

    otp_request = OTPRequest(
        phone=data.phone,
        otp_code=otp,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        verified=False,
    )

    db.add(otp_request)
    db.commit()

    # send via SMS (and email if a user exists with that phone)
    try:
        send_sms(to=data.phone, message=f"Your verification code is: {otp}")
    except Exception as e:
        logger.exception("send_sms failed for %s: %s", data.phone, e)

    # try find user by phone to send email if available
    user = db.query(User).filter(User.phone == data.phone).first()
    if user:
        try:
            send_email(
                to=user.email,
                subject="Your verification code",
                body=f"Your verification code is: {otp}",
            )
        except Exception as e:
            logger.exception("send_email failed for %s: %s", user.email, e)

    return {"message": "OTP sent successfully", "dev_otp": otp if settings.DEBUG else None}


@router.post("/verify-otp")
def verify_otp(data: VerifyOTPRequest, db: Session = Depends(get_db)):
    otp_request = (
        db.query(OTPRequest)
        .filter(
            OTPRequest.phone == data.phone,
            OTPRequest.otp_code == data.otp_code,
            OTPRequest.verified == False,
        )
        .order_by(OTPRequest.created_at.desc())
        .first()
    )

    if not otp_request:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if otp_request.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="OTP expired")

    otp_request.verified = True

    user = db.query(User).filter(User.phone == data.phone).first()
    if user:
        user.is_verified = True
        user.status = UserStatus.active

    db.commit()

    return {"message": "OTP verified successfully"}


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.strip().lower()).first()

    if not user:
        return {"message": "If email exists, OTP has been sent"}

    otp = generate_otp()

    otp_request = OTPRequest(
        user_id=user.id,
        phone=user.phone,
        otp_code=otp,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        verified=False,
    )

    db.add(otp_request)
    db.commit()

    # send password-reset OTP via email and SMS
    try:
        send_email(
            to=user.email,
            subject="Password reset code",
            body=f"Your password reset code is: {otp}",
        )
    except Exception as e:
        logger.exception("send_email failed for %s: %s", user.email, e)

    try:
        send_sms(
            to=user.phone,
            message=f"Your password reset code is: {otp}",
        )
    except Exception as e:
        logger.exception("send_sms failed for %s: %s", user.phone, e)

    return {"message": "Password reset OTP sent", "dev_otp": otp if settings.DEBUG else None}


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.strip().lower()).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    otp_request = (
        db.query(OTPRequest)
        .filter(
            OTPRequest.user_id == user.id,
            OTPRequest.otp_code == data.otp_code,
            OTPRequest.verified == False,
        )
        .order_by(OTPRequest.created_at.desc())
        .first()
    )

    if not otp_request:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if otp_request.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="OTP expired")

    user.password_hash = hash_password(data.new_password)
    otp_request.verified = True

    db.commit()

    return {"message": "Password reset successfully"}