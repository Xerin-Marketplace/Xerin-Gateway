import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
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
    SellerProfile,
    SellerStatus,
    BusinessCategory,
    SellerBusinessCategory,
    UserRole,
    Role,
    RolePermission,
    UserPermission,
)
from api.schemas import *
from api.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    generate_otp,
    hash_token,
    hash_otp,
    verify_otp_hash,
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

_rate_lock = threading.Lock()
_rate_buckets: dict[str, deque] = defaultdict(deque)
_otp_attempts: dict[str, list] = defaultdict(list)

OTP_MAX_ATTEMPTS = 5
OTP_ATTEMPT_WINDOW_SECONDS = 10 * 60  # 10 minutes

_redis_client = None
_redis_url = getattr(settings, "REDIS_URL", None)
if _redis_url:
    try:
        import redis as _redis_lib

        _redis_client = _redis_lib.from_url(_redis_url, socket_timeout=0.5)
        _redis_client.ping()
        logger.info("Auth rate limiter: using Redis at %s", _redis_url)
    except Exception as e:
        logger.warning(
            "Auth rate limiter: could not connect to Redis (%s). "
            "Falling back to in-memory rate limiting.",
            e,
        )
else:
    logger.info(
        "Auth rate limiter: REDIS_URL not configured, using in-memory "
        "rate limiting (single-process only)."
    )


def _redis_sliding_window_count(key: str, window_seconds: int) -> int | None:
    """
    Record a hit and return the count of hits within the window using a
    Redis sorted set. Returns None if Redis is unavailable or the call
    fails, signaling the caller to use the in-memory fallback instead.
    """
    if _redis_client is None:
        return None
    now = time.time()
    redis_key = f"authrl:{key}"
    try:
        pipe = _redis_client.pipeline()
        pipe.zadd(redis_key, {f"{now}:{id(object())}": now})
        pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
        pipe.zcard(redis_key)
        pipe.expire(redis_key, window_seconds)
        _, _, count, _ = pipe.execute()
        return int(count)
    except Exception as e:
        logger.warning("Redis rate limit check failed for %s: %s", key, e)
        return None


def _rate_limit(key: str, max_calls: int, window_seconds: int) -> None:
    """Sliding-window rate limiter (Redis if available, else in-memory). Raises 429 if exceeded."""
    count = _redis_sliding_window_count(key, window_seconds)
    if count is not None:
        if count > max_calls:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
            )
        return

    # in-memory fallback
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
    key = f"otp-fail:{phone}"

    if _redis_client is not None:
        try:
            count = _redis_client.zcount(
                f"authrl:{key}", time.time() - OTP_ATTEMPT_WINDOW_SECONDS, "+inf"
            )
            if count >= OTP_MAX_ATTEMPTS:
                raise HTTPException(
                    status_code=429,
                    detail="Too many failed OTP attempts. Please try again later.",
                )
            return
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("Redis OTP lockout check failed for %s: %s", phone, e)
            # fall through to in-memory below

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
    key = f"otp-fail:{phone}"
    if _redis_sliding_window_count(key, OTP_ATTEMPT_WINDOW_SECONDS) is not None:
        return  # already recorded by the sliding-window call above
    with _rate_lock:
        _otp_attempts[phone].append(time.time())


def _clear_otp_failures(phone: str) -> None:
    if _redis_client is not None:
        try:
            _redis_client.delete(f"authrl:otp-fail:{phone}")
        except Exception as e:
            logger.warning("Redis OTP failure clear failed for %s: %s", phone, e)
    with _rate_lock:
        _otp_attempts.pop(phone, None)


def _invalidate_existing_otps(
    db: Session, phone: str, purpose: str = "generic"
) -> None:
    """
    Mark any previously-issued, unverified OTPs for this phone AND this
    purpose as used/invalid, so only the most recently issued OTP for that
    specific purpose is ever valid. Scoping by purpose means invalidating a
    "register" OTP doesn't touch a still-pending "password_reset" OTP for
    the same phone.
    """
    db.query(OTPRequest).filter(
        OTPRequest.phone == phone,
        OTPRequest.purpose == purpose,
        OTPRequest.verified.is_(False),
    ).update({"verified": True})


def _client_ip(request: Request) -> str:
    """
    Best-effort client IP.

    X-Forwarded-For is only trusted when settings.TRUST_PROXY_HEADERS is
    explicitly enabled — set this only if you are actually behind a
    reverse proxy / load balancer that sets this header correctly.
    Otherwise a client could set an arbitrary X-Forwarded-For value and
    dodge IP-based rate limiting entirely, so we ignore it by default and
    use the raw socket peer address instead.
    """
    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # x-forwarded-for can be a comma-separated chain; the first
            # entry is the original client.
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def cleanup_old_otp_requests(db: Session, older_than_days: int = 30) -> int:
    """
    Delete OTP rows older than `older_than_days`.

    This is NOT called automatically anywhere in this router — it's meant
    to be invoked from a periodic job (cron, Celery beat, APScheduler,
    a k8s CronJob, etc.) so the otp_requests table doesn't grow forever.
    Returns the number of rows deleted.

    Example wiring (outside this file):
        from api.routers.auth import cleanup_old_otp_requests
        from api.database import SessionLocal

        def run_otp_cleanup():
            db = SessionLocal()
            try:
                deleted = cleanup_old_otp_requests(db)
                logger.info("Deleted %d stale OTP rows", deleted)
            finally:
                db.close()
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    deleted = (
        db.query(OTPRequest)
        .filter(OTPRequest.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


def _get_required_role(db: Session, role_name: str) -> Role:
    role = db.query(Role).filter(Role.name == role_name).first()
    if role is None:
        raise RuntimeError(
            f"Required role '{role_name}' does not exist. "
            "Run: python -m api.seed_permissions"
        )
    return role


def _assign_role(db: Session, user_id, role_name: str) -> None:
    role = _get_required_role(db, role_name)
    exists = (
        db.query(UserRole)
        .filter(
            UserRole.user_id == user_id,
            UserRole.role_id == role.id,
        )
        .first()
    )
    if exists is None:
        db.add(UserRole(user_id=user_id, role_id=role.id))


@router.post("/register", response_model=RegistrationResponse)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    phone = (data.phone or "").strip()
    if not phone:
        raise HTTPException(status_code=422, detail="Phone number is required")

    existing_user = (
        db.query(User).filter((User.email == email) | (User.phone == phone)).first()
    )

    resumed_registration = False

    if existing_user:
        same_identity = existing_user.email == email and existing_user.phone == phone
        still_pending = (
            not existing_user.is_verified
            and existing_user.status == UserStatus.pending_verification
        )

        if not (same_identity and still_pending):
            raise HTTPException(
                status_code=409,
                detail="An account with this Email or phone already exists. Please sign in.",
            )

        # The account was already committed during an earlier registration
        # attempt but has not completed OTP verification. Resume instead of
        # rejecting the user as a duplicate.
        user = existing_user
        user.first_name = data.first_name.strip()
        user.last_name = data.last_name.strip()
        user.password_hash = hash_password(data.password)
        _assign_role(db, user.id, "customer")
        resumed_registration = True
    else:
        user = User(
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            email=email,
            phone=phone,
            password_hash=hash_password(data.password),
            status=UserStatus.pending_verification,
            is_verified=False,
        )
        db.add(user)
        db.flush()
        _assign_role(db, user.id, "customer")

    otp = generate_otp()

    try:
        _invalidate_existing_otps(db, phone, purpose="register")
        db.add(
            OTPRequest(
                user_id=user.id,
                phone=phone,
                otp_hash=hash_otp(otp),
                purpose="register",
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
                verified=False,
            )
        )
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        logger.exception("Customer registration failed for %s / %s", email, phone)
        raise HTTPException(
            status_code=500,
            detail="Registration failed. Please try again.",
        )

    try:
        send_email(
            to=email,
            subject="Verify your account",
            body=f"Your verification code is: {otp}",
        )
    except Exception as exc:
        logger.exception("send_email failed for %s: %s", email, exc)

    try:
        send_sms(
            to=phone,
            message=f"Use this OTP to verify your Xerin Marketplace account: {otp}",
        )
    except Exception as exc:
        logger.exception("send_sms failed for %s: %s", phone, exc)

    return RegistrationResponse(
        message=(
            "Registration resumed. A fresh verification code has been sent."
            if resumed_registration
            else "Account created. Enter the verification code to continue."
        ),
        user_id=user.id,
        email=user.email,
        phone=user.phone,
        resumed_registration=resumed_registration,
    )


@router.post("/register-seller", response_model=SellerRegistrationResponse)
def register_seller(data: SellerRegisterRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    phone = data.phone.strip()

    if not data.agreement_accepted:
        raise HTTPException(status_code=400, detail="Seller agreement must be accepted")

    if not data.business_category_ids:
        raise HTTPException(
            status_code=400, detail="At least one business category is required"
        )

    categories = (
        db.query(BusinessCategory)
        .filter(BusinessCategory.id.in_(data.business_category_ids))
        .all()
    )

    if len(categories) != len(set(data.business_category_ids)):
        raise HTTPException(
            status_code=400, detail="One or more business categories are invalid"
        )

    existing_user = (
        db.query(User).filter((User.email == email) | (User.phone == phone)).first()
    )

    resumed_registration = False

    if existing_user:
        same_identity = existing_user.email == email and existing_user.phone == phone
        still_pending = (
            not existing_user.is_verified
            and existing_user.status == UserStatus.pending_verification
        )

        if not (same_identity and still_pending):
            raise HTTPException(
                status_code=409,
                detail="An account with this Email or phone already exists. Please sign in.",
            )

        seller = db.query(Seller).filter(Seller.user_id == existing_user.id).first()
        if seller is None:
            raise HTTPException(
                status_code=409,
                detail="This pending account is not a seller registration. Please sign in or use another account.",
            )

        # Safe retry after a committed-but-apparently-failed first request.
        user = existing_user
        resumed_registration = True
    else:
        user = User(
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            email=email,
            phone=phone,
            password_hash=hash_password(data.password),
            status=UserStatus.pending_verification,
            is_verified=False,
        )
        db.add(user)
        db.flush()
        _assign_role(db, user.id, "seller")

        seller = Seller(
            user_id=user.id,
            business_name=data.business_name,
            # The account email/phone are valid business contact values too.
            contact_email=data.contact_email or email,
            contact_phone=data.contact_phone or phone,
            agreement_accepted=True,
            status=SellerStatus.pending,
        )
        db.add(seller)
        db.flush()

        seller_profile = SellerProfile(
            seller_id=seller.id,
            business_description=data.business_description,
            business_country=data.business_country,
            business_region=data.business_region,
            business_city=data.business_city,
            business_address=data.business_address,
            product_description=data.product_description,
            years_in_business=data.years_in_business,
            website_url=data.website_url,
        )
        db.add(seller_profile)

        for category_id in set(data.business_category_ids):
            db.add(
                SellerBusinessCategory(
                    seller_id=seller.id,
                    business_category_id=category_id,
                )
            )

    otp = generate_otp()

    try:
        _invalidate_existing_otps(db, phone, purpose="register_seller")
        db.add(
            OTPRequest(
                user_id=user.id,
                phone=phone,
                otp_hash=hash_otp(otp),
                purpose="register_seller",
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
                verified=False,
            )
        )
        db.commit()
        db.refresh(user)
        db.refresh(seller)
    except Exception:
        db.rollback()
        logger.exception("Seller registration failed for %s / %s", email, phone)
        raise HTTPException(
            status_code=500,
            detail="Seller registration failed. Please try again.",
        )

    try:
        send_email(
            to=email,
            subject="Verify your seller account",
            body=f"Your seller verification code is: {otp}",
        )
    except Exception as exc:
        logger.exception("send_email failed for %s: %s", email, exc)

    try:
        send_sms(
            to=phone,
            message=f"Use this OTP to verify your Xerin Marketplace seller account: {otp}",
        )
    except Exception as exc:
        logger.exception("send_sms failed for %s: %s", phone, exc)

    return SellerRegistrationResponse(
        message=(
            "Seller registration resumed. A fresh verification code has been sent."
            if resumed_registration
            else "Seller account created. Enter the verification code to continue."
        ),
        user_id=user.id,
        seller_id=seller.id,
        email=user.email,
        phone=user.phone,
        seller_status=seller.status.value
        if hasattr(seller.status, "value")
        else str(seller.status),
        resumed_registration=resumed_registration,
    )


def build_auth_user_response(db: Session, user: User):
    seller = db.query(Seller).filter(Seller.user_id == user.id).first()

    user_roles = db.query(UserRole).filter(UserRole.user_id == user.id).all()

    roles = [user_role.role.name for user_role in user_roles]

    role_ids = [user_role.role_id for user_role in user_roles]

    permissions = []

    if role_ids:
        role_permissions = (
            db.query(RolePermission).filter(RolePermission.role_id.in_(role_ids)).all()
        )

        permissions = {
            role_permission.permission.code
            for role_permission in role_permissions
            if role_permission.permission is not None
        }
    else:
        permissions = set()

    direct_permissions = (
        db.query(UserPermission).filter(UserPermission.user_id == user.id).all()
    )
    permissions.update(
        row.permission.code for row in direct_permissions if row.permission is not None
    )
    permissions = sorted(permissions)

    if "super_admin" in roles:
        account_type = "super_admin"
    elif "admin" in roles:
        account_type = "admin"
    elif seller:
        account_type = "seller"
    else:
        account_type = "customer"

    return {
        "id": str(user.id),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": user.phone,
        "is_verified": user.is_verified,
        "status": user.status.value if user.status else None,
        "account_type": account_type,
        "is_seller": seller is not None,
        "seller_status": seller.status.value if seller else None,
        "roles": roles,
        "permissions": permissions,
    }


@router.post("/login", response_model=TokenResponse)
def login(request: Request, data: LoginRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    ip = _client_ip(request)

    _rate_limit(f"login:email:{email}", max_calls=10, window_seconds=5 * 60)
    _rate_limit(f"login:ip:{ip}", max_calls=30, window_seconds=5 * 60)

    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.status == UserStatus.suspended:
        raise HTTPException(status_code=403, detail="Account suspended")

    inactive_status = getattr(UserStatus, "inactive", None)
    if inactive_status is not None and user.status == inactive_status:
        raise HTTPException(status_code=403, detail="Account inactive")

    if user.status == UserStatus.pending_verification or not user.is_verified:
        raise HTTPException(status_code=403, detail="Account not verified")

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )

    user.last_login_at = datetime.now(timezone.utc)

    db.add(session)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": build_auth_user_response(db, user),
    }


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
            UserSession.token_hash == hash_token(data.refresh_token),
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
            data.refresh_token,
            settings.refresh_token_secret,
            algorithms=[ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
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
            UserSession.token_hash == hash_token(data.refresh_token),
        )
        .first()
    )

    if not session:
        raise HTTPException(status_code=401, detail="Refresh token not found")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=401, detail="User not found")
    if user.status in {UserStatus.suspended, UserStatus.inactive}:
        raise HTTPException(status_code=403, detail="Account is not active")
    if not user.is_verified or user.status == UserStatus.pending_verification:
        raise HTTPException(status_code=403, detail="Account not verified")

    # FIX: previously the DB session's own expiry was never checked here —
    # a session record past its expires_at could still be used to mint new
    # tokens forever as long as the JWT itself decoded successfully.
    if session.expires_at < datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token expired")

    access_token = create_access_token({"sub": str(user_id)})
    new_refresh_token = create_refresh_token({"sub": str(user_id)})

    session.token_hash = hash_token(new_refresh_token)
    session.expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    db.commit()

    return {"access_token": access_token, "refresh_token": new_refresh_token}


@router.post("/send-otp")
def send_otp(request: Request, data: SendOTPRequest, db: Session = Depends(get_db)):
    phone = data.phone.strip()
    ip = _client_ip(request)

    # If SendOTPRequest has a `purpose` field, use it; otherwise default to
    # "generic". Add `purpose: str` to the SendOTPRequest schema if you want
    # callers to specify why they're requesting an OTP (e.g. "phone_verify").
    purpose = data.purpose

    _rate_limit(f"send-otp:phone:{phone}", max_calls=3, window_seconds=5 * 60)
    _rate_limit(f"send-otp:ip:{ip}", max_calls=10, window_seconds=5 * 60)

    # invalidate any stale OTPs for this phone before issuing a new one
    _invalidate_existing_otps(db, phone, purpose=purpose)
    _clear_otp_failures(phone)

    otp = generate_otp()

    otp_request = OTPRequest(
        phone=phone,
        otp_hash=hash_otp(otp),
        purpose=purpose,
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

    return {
        "message": "OTP sent successfully",
        "dev_otp": otp if settings.DEBUG else None,
    }


@router.post("/verify-otp")
def verify_otp(data: VerifyOTPRequest, db: Session = Depends(get_db)):
    phone = data.phone.strip()

    # If VerifyOTPRequest has a `purpose` field, scope the lookup to it —
    # this is what stops a "password_reset" OTP from being accepted here
    # as if it were a "register" OTP. If the schema doesn't have a
    # `purpose` field yet, this falls back to the old behavior (matches
    # any unverified OTP for the phone, regardless of what it was for).
    # Add `purpose: str | None = None` to VerifyOTPRequest to enable this.
    purpose = data.purpose

    # Brute-force protection: block after too many failed attempts.
    _check_otp_lockout(phone)

    query = db.query(OTPRequest).filter(
        OTPRequest.phone == phone,
        OTPRequest.verified.is_(False),
    )
    if purpose:
        query = query.filter(OTPRequest.purpose == purpose)

    otp_request = query.order_by(OTPRequest.created_at.desc()).first()

    if not otp_request or not verify_otp_hash(data.otp_code, otp_request.otp_hash):
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
def forgot_password(
    request: Request, data: ForgotPasswordRequest, db: Session = Depends(get_db)
):
    email = data.email.strip().lower()
    ip = _client_ip(request)

    _rate_limit(f"forgot-password:email:{email}", max_calls=3, window_seconds=15 * 60)
    _rate_limit(f"forgot-password:ip:{ip}", max_calls=10, window_seconds=15 * 60)

    user = db.query(User).filter(User.email == email).first()

    if not user:
        return {"message": "If email exists, OTP has been sent"}

    _invalidate_existing_otps(db, user.phone, purpose="password_reset")

    otp = generate_otp()

    otp_request = OTPRequest(
        user_id=user.id,
        phone=user.phone,
        otp_hash=hash_otp(otp),
        purpose="password_reset",
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

    return {
        "message": "Password reset OTP sent",
        "dev_otp": otp if settings.DEBUG else None,
    }


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.strip().lower()).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    otp_request = (
        db.query(OTPRequest)
        .filter(
            OTPRequest.user_id == user.id,
            OTPRequest.purpose == "password_reset",
            OTPRequest.verified.is_(False),
        )
        .order_by(OTPRequest.created_at.desc())
        .first()
    )

    if not otp_request or not verify_otp_hash(data.otp_code, otp_request.otp_hash):
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


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=400,
            detail="New password must be different from current password",
        )

    user.password_hash = hash_password(data.new_password)

    # invalidate all refresh sessions after password change
    db.query(UserSession).filter(UserSession.user_id == user.id).delete()

    db.commit()
    return {"message": "Password changed successfully. Please log in again."}
