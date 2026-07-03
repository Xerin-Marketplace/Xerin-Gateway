import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from jose import jwt, JWTError
import logging

from api.database import SessionLocal
from api.deps import get_db, get_current_user
from api.models import (
    User,
    Session as UserSession,
    OTPRequest,
    UserStatus,
    Seller,
    SellerStatus,
    Category,
    SellerBusinessCategory,
)
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


# ---------------------------------------------------------------------------
# Rate limiting / brute-force protection
#
# NOTE: This is an IN-MEMORY, single-process limiter. It is good enough to
# stop a lone bot from hammering an endpoint during dev/testing, but it does
# NOT work correctly if you run more than one worker/process/instance,
# because each process keeps its own counters. For production, replace this
# with Redis (e.g. via `slowapi` + redis, or `fastapi-limiter`) or persist
# attempt counts in the database (e.g. an `attempts` column on OTPRequest).
# ---------------------------------------------------------------------------
_rate_lock = threading.Lock()
_rate_buckets: dict[str, deque] = defaultdict(deque)
_otp_attempts: dict[str, list] = defaultdict(list)  # phone -> [attempt_timestamps]

OTP_MAX_ATTEMPTS = 5
OTP_ATTEMPT_WINDOW_SECONDS = 10 * 60  # 10 minutes


def _rate_limit(key: str, max_calls: int, window_seconds: int) -> None:
    """Simple sliding-window rate limiter. Raises 429 if exceeded."""
    now = time.time()
    with _rate_lock:
        bucket = _rate_buckets[key]
        while bucket and bucket[0] < now - window_seconds:
            bucket.popleft()
        if len(bucket) >= max_calls:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
            )
        bucket.append(now)


def _check_otp_lockout(phone: str) -> None:
    """Raise 429 if this phone has exceeded failed OTP verification attempts."""
    now = time.time()
    with _rate_lock:
        attempts = _otp_attempts[phone]
        while attempts and attempts[0] < now - OTP_ATTEMPT_WINDOW_SECONDS:
            attempts.pop(0)
        if len(attempts) >= OTP_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail="Too many failed OTP attempts. Please try again later.",
            )


def _record_otp_failure(phone: str) -> None:
    with _rate_lock:
        _otp_attempts[phone].append(time.time())


def _clear_otp_failures(phone: str) -> None:
    with _rate_lock:
        _otp_attempts.pop(phone, None)


def _invalidate_existing_otps(db: Session, phone: str) -> None:
    """
    Mark any previously-issued, unverified OTPs for this phone as
    used/invalid, so only the most recently issued OTP is ever valid.
    """
    db.query(OTPRequest).filter(
        OTPRequest.phone == phone,
        OTPRequest.verified == False,  # noqa: E712
    ).update({"verified": True})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

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

    # invalidate any stale OTPs for this phone, then generate a fresh one
    _invalidate_existing_otps(db, phone)

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


@router.post("/register-seller", response_model=SellerResponse)
def register_seller(data: SellerRegisterRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    phone = data.phone.strip()

    existing_user = (
        db.query(User)
        .filter((User.email == email) | (User.phone == phone))
        .first()
    )

    if existing_user:
        raise HTTPException(status_code=400, detail="Email or phone already exists")

    if not data.agreement_accepted:
        raise HTTPException(status_code=400, detail="Seller agreement must be accepted")

    if not data.business_category_ids:
        raise HTTPException(status_code=400, detail="At least one business category is required")

    categories = db.query(Category).filter(
        Category.id.in_(data.business_category_ids)
    ).all()

    if len(categories) != len(set(data.business_category_ids)):
        raise HTTPException(status_code=400, detail="One or more business categories are invalid")

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

    seller = Seller(
        user_id=user.id,
        business_name=data.business_name,
        business_description=data.business_description,
        business_location=data.business_location,
        business_country=data.business_country,
        business_region=data.business_region,
        business_city=data.business_city,
        business_address=data.business_address,
        product_description=data.product_description,
        years_in_business=data.years_in_business,
        website_url=data.website_url,
        contact_email=data.contact_email or email,
        contact_phone=data.contact_phone or phone,
        agreement_accepted=data.agreement_accepted,
        status=SellerStatus.pending,
    )

    db.add(seller)
    db.commit()
    db.refresh(seller)

    for category_id in set(data.business_category_ids):
        db.add(
            SellerBusinessCategory(
                seller_id=seller.id,
                category_id=category_id,
            )
        )

    # FIX: these inserts were never committed before — the category links
    # would silently be lost once the session closed.
    db.commit()

    # invalidate any stale OTPs for this phone, then generate a fresh one
    _invalidate_existing_otps(db, phone)

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
    db.refresh(seller)

    try:
        send_email(
            to=email,
            subject="Verify your seller account",
            body=f"Your seller verification code is: {otp}",
        )
    except Exception as e:
        logger.exception("send_email failed for %s: %s", email, e)

    try:
        send_sms(
            to=phone,
            message=f"Use this OTP to verify your Xerin Market seller account: {otp}",
        )
    except Exception as e:
        logger.exception("send_sms failed for %s: %s", phone, e)

    return seller


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()

    # Rate-limit by email to slow down credential-stuffing / brute force.
    _rate_limit(f"login:{email}", max_calls=10, window_seconds=5 * 60)

    user = db.query(User).filter(User.email == email).first()

    # Generic error message on purpose: don't reveal whether the account
    # exists or whether it was the email or the password that was wrong.
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.status == UserStatus.suspended:
        raise HTTPException(status_code=403, detail="Account suspended")

    # Enforce verification before allowing login
    if not user.is_verified:
        raise HTTPException(status_code=405, detail="Account not verified")

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

    # FIX: previously the DB session's own expiry was never checked here —
    # a session record past its expires_at could still be used to mint new
    # tokens forever as long as the JWT itself decoded successfully.
    if session.expires_at < datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token expired")

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
    phone = data.phone.strip()

    _rate_limit(f"send-otp:{phone}", max_calls=3, window_seconds=5 * 60)

    # invalidate any stale OTPs for this phone before issuing a new one
    _invalidate_existing_otps(db, phone)
    _clear_otp_failures(phone)

    otp = generate_otp()

    otp_request = OTPRequest(
        phone=phone,
        otp_code=otp,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        verified=False,
    )

    db.add(otp_request)
    db.commit()

    # send via SMS (and email if a user exists with that phone)
    try:
        send_sms(to=phone, message=f"Your verification code is: {otp}")
    except Exception as e:
        logger.exception("send_sms failed for %s: %s", phone, e)

    # try find user by phone to send email if available
    user = db.query(User).filter(User.phone == phone).first()
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
    phone = data.phone.strip()

    # Brute-force protection: block after too many failed attempts.
    _check_otp_lockout(phone)

    otp_request = (
        db.query(OTPRequest)
        .filter(
            OTPRequest.phone == phone,
            OTPRequest.otp_code == data.otp_code,
            OTPRequest.verified == False,  # noqa: E712
        )
        .order_by(OTPRequest.created_at.desc())
        .first()
    )

    if not otp_request:
        _record_otp_failure(phone)
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if otp_request.expires_at < datetime.now(timezone.utc):
        _record_otp_failure(phone)
        raise HTTPException(status_code=400, detail="OTP expired")

    otp_request.verified = True

    user = db.query(User).filter(User.phone == phone).first()
    if user:
        user.is_verified = True
        user.status = UserStatus.active

    db.commit()
    _clear_otp_failures(phone)

    return {"message": "OTP verified successfully"}


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()

    _rate_limit(f"forgot-password:{email}", max_calls=3, window_seconds=15 * 60)

    user = db.query(User).filter(User.email == email).first()

    if not user:
        return {"message": "If email exists, OTP has been sent"}

    _invalidate_existing_otps(db, user.phone)

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
            OTPRequest.verified == False,  # noqa: E712
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

    # FIX: invalidate every existing session for this user after a password
    # reset, so a previously-stolen refresh token stops working immediately.
    db.query(UserSession).filter(UserSession.user_id == user.id).delete()

    db.commit()

    return {"message": "Password reset successfully"}