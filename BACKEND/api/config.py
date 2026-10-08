from __future__ import annotations

from pathlib import Path
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Xerin Mart API"
    APP_ENV: Literal["development", "testing", "staging", "production"] = "development"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    PUBLIC_BASE_URL: str | None = None
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = Field(default=10, ge=1)
    DB_MAX_OVERFLOW: int = Field(default=20, ge=0)
    DB_POOL_RECYCLE_SECONDS: int = Field(default=1800, ge=60)
    DB_ECHO: bool = False

    # JWT
    # SECRET_KEY is retained for backward compatibility with the current auth.py.
    # ACCESS_TOKEN_SECRET and REFRESH_TOKEN_SECRET can be configured separately
    # after auth.py is updated to decode them independently.
    SECRET_KEY: str = Field(min_length=32)
    ACCESS_TOKEN_SECRET: str | None = None
    REFRESH_TOKEN_SECRET: str | None = None
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "xerin-marketplace"
    JWT_AUDIENCE: str = "xerin-marketplace-api"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=1)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1)

    # Browser and proxy security
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,https://xerinmart.com,https://www.xerinmart.com,https://xerinmarketplace.com,https://www.xerinmarketplace.com"
    TRUSTED_HOSTS: str = "localhost,127.0.0.1,xerinmart.com,www.xerinmart.com,xerinmarketplace.com,www.xerinmarketplace.com,api.xerinmarketplace.com"
    TRUST_PROXY_HEADERS: bool = False

    # Local uploads (temporary until object storage is introduced)
    UPLOAD_DIRECTORY: str = "uploads"
    SERVE_LOCAL_UPLOADS: bool = True
    DEFAULT_COUNTRY: str = "Tanzania"
    MAX_UPLOAD_SIZE_MB: int = Field(default=5, ge=1)

    # Inventory reservations
    INVENTORY_RESERVATION_MINUTES: int = Field(default=1440, ge=5, le=1440)
    SELLER_SETTLEMENT_DAYS: int = Field(default=7, ge=0, le=90)
    MINIMUM_PAYOUT_AMOUNT: Decimal = Field(default=Decimal("1000.00"), ge=0)

    # Redis
    REDIS_URL: str | None = None

    # Email
    EMAIL_HOST: str | None = None
    EMAIL_PORT: int = Field(default=587, ge=1, le=65535)
    EMAIL_USER: str | None = None
    EMAIL_PASSWORD: str | None = None
    EMAIL_FROM: str | None = None
    EMAIL_FROM_NAME: str = "Xerin Mart - Tanzania"
    EMAIL_REPLY_TO: str | None = None
    EMAIL_USE_TLS: bool = True
    EMAIL_USE_SSL: bool = False

    # SMS (Africa's Talking)
    AT_USERNAME: str | None = None
    AT_API_KEY: str | None = None
    AT_SENDER_ID: str | None = None

    # Google OAuth (server-side ID token verification). Feature is disabled
    # when unset — the frontend should not render the Google button.
    GOOGLE_CLIENT_ID: str | None = None

    # Monitoring / alerting
    MONITORING_ENABLED: bool = True
    # Central destination for operational/security alert emails. Leave unset
    # to keep auditing but disable email delivery entirely.
    MONITORING_ALERT_EMAIL: str | None = None
    # Minimum audit/security severity that triggers an email alert.
    MONITORING_ALERT_MIN_SEVERITY: str = "warning"
    # Alert deduplication: same dedup key inside this window is aggregated
    # into one notification instead of one email per event.
    MONITORING_ALERT_WINDOW_MINUTES: int = Field(default=15, ge=1)
    # Hard cap on how many emails a single dedup key may emit per window.
    MONITORING_ALERT_MAX_PER_WINDOW: int = Field(default=2, ge=1)
    # Email retry backoff (seconds): attempt n waits BASE * 2^(n-1).
    ALERT_EMAIL_MAX_ATTEMPTS: int = Field(default=5, ge=1)
    ALERT_EMAIL_RETRY_BASE_SECONDS: int = Field(default=60, ge=5)
    # Weekly operational report.
    MONITORING_WEEKLY_REPORT_ENABLED: bool = False
    MONITORING_WEEKLY_REPORT_DAY: str = "MONDAY"
    MONITORING_WEEKLY_REPORT_TIME: str = "08:00"
    # Audit retention (days). 0 disables automatic cleanup.
    AUDIT_LOG_RETENTION_DAYS: int = Field(default=365, ge=0)
    # Deployment version label written into migration/deploy events.
    APP_VERSION: str | None = None
    SMS_API_URL: str | None = None

    # Payment webhook security
    PAYMENT_WEBHOOK_SECRET: str | None = None
    PAYMENT_ORDER_TIMEOUT_MINUTES: int = 1440
    PAYMENT_ATTEMPT_RETRY_AFTER_SECONDS: int = 90

    # AzamPay (MNO push + hosted card checkout)
    AZAMPAY_SANDBOX: bool = True
    AZAMPAY_APP_NAME: str | None = None
    AZAMPAY_CLIENT_ID: str | None = None
    AZAMPAY_CLIENT_SECRET: str | None = None
    AZAMPAY_API_KEY: str | None = None
    AZAMPAY_VENDOR_ID: str | None = None
    AZAMPAY_VENDOR_NAME: str | None = None
    AZAMPAY_REQUEST_ORIGIN: str | None = None
    AZAMPAY_CARD_SUCCESS_URL: str | None = None
    AZAMPAY_CARD_FAILURE_URL: str | None = None
    AZAMPAY_CALLBACK_SECRET: str | None = None
    AZAMPAY_LANGUAGE: str = "en"
    AZAMPAY_SANDBOX_AUTH_URL: str = "https://authenticator-sandbox.azampay.co.tz/AppRegistration/GenerateToken"

    # Selcom (default gateway: USSD push mobile money + hosted card checkout)
    DEFAULT_PAYMENT_PROVIDER: str | None = None
    MNO_PAYMENT_PROVIDER: str | None = None
    SELCOM_API_KEY: str | None = None
    SELCOM_API_SECRET: str | None = None
    SELCOM_VENDOR: str | None = None
    SELCOM_VENDOR_ID: str | None = None
    SELCOM_BASE_URL: str = "https://apigw.selcommobile.com"
    SELCOM_CREATE_ORDER_PATH: str = "/v1/checkout/create-order-minimal"
    SELCOM_WALLET_PAYMENT_PATH: str = "/v1/checkout/wallet-payment"
    SELCOM_ORDER_STATUS_PATH: str = "/v1/checkout/order-status"
    SELCOM_WEBHOOK_URL: str | None = None
    SELCOM_REDIRECT_URL: str | None = None
    SELCOM_CANCEL_URL: str | None = None
    SELCOM_ORDER_EXPIRY_MINUTES: int = 60
    SELCOM_TIMEOUT_SECONDS: int = 30
    SELCOM_MAX_AMOUNT_TZS: float | None = None

    # ── Map / geocoding (checkout address pin, seller pickup points) ──
    # Google Places is used when a key is configured; otherwise the API
    # falls back to Nominatim (OpenStreetMap) — free, no key required.
    GOOGLE_MAPS_API_KEY: str | None = None
    NOMINATIM_BASE_URL: str = "https://nominatim.openstreetmap.org"
    NOMINATIM_USER_AGENT: str = "XerinMart/1.0 (+https://xerinmart.com)"
    MAP_REQUEST_TIMEOUT: int = 12

    @property
    def payment_provider(self) -> str:
        return (
            self.DEFAULT_PAYMENT_PROVIDER
            or self.MNO_PAYMENT_PROVIDER
            or "selcom"
        ).strip().lower()

    @property
    def selcom_vendor(self) -> str:
        return self.SELCOM_VENDOR or self.SELCOM_VENDOR_ID or ""
    AZAMPAY_LIVE_AUTH_URL: str = "https://authenticator.azampay.co.tz/AppRegistration/GenerateToken"
    AZAMPAY_SANDBOX_BASE_URL: str = "https://sandbox.azampay.co.tz"
    AZAMPAY_LIVE_BASE_URL: str = "https://checkout.azampay.co.tz"
    AZAMPAY_MNO_CHECKOUT_PATH: str = "/azampay/mno/checkout"
    AZAMPAY_POST_CHECKOUT_PATH: str = "/azampay/checkout"
    AZAMPAY_TIMEOUT_SECONDS: int = Field(default=30, ge=1, le=120)

    # External delivery provider
    DELIVERY_PROVIDER_NAME: str = "xerin-express"
    DELIVERY_API_BASE_URL: str | None = None
    DELIVERY_API_KEY: str | None = None
    DELIVERY_API_KEY_HEADER: str = "Authorization"
    DELIVERY_WEBHOOK_SECRET: str | None = None
    DELIVERY_QUOTE_PATH: str = "/quotes"
    DELIVERY_CREATE_PATH: str = "/deliveries"
    DELIVERY_API_TIMEOUT_SECONDS: int = Field(default=30, ge=1, le=120)

    # Initial super-admin bootstrap
    SUPER_ADMIN_EMAIL: str | None = None
    SUPER_ADMIN_PHONE: str | None = None
    SUPER_ADMIN_PASSWORD: str | None = None
    SUPER_ADMIN_FIRST_NAME: str = "Super"
    SUPER_ADMIN_LAST_NAME: str = "Admin"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("API_PREFIX")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        if not value.startswith("/"):
            value = f"/{value}"
        return value.rstrip("/")

    @field_validator("EMAIL_USE_SSL")
    @classmethod
    def validate_email_security(cls, value: bool, info):
        tls = info.data.get("EMAIL_USE_TLS", True)
        if value and tls:
            raise ValueError("EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be true")
        return value

    @property
    def access_token_secret(self) -> str:
        return self.ACCESS_TOKEN_SECRET or self.SECRET_KEY

    @property
    def refresh_token_secret(self) -> str:
        return self.REFRESH_TOKEN_SECRET or self.SECRET_KEY

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.CORS_ORIGINS.split(",") if item.strip()]

    @property
    def trusted_hosts(self) -> list[str]:
        return [item.strip() for item in self.TRUSTED_HOSTS.split(",") if item.strip()]

    @property
    def upload_path(self) -> Path:
        return Path(self.UPLOAD_DIRECTORY).expanduser().resolve()

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


settings = Settings()
