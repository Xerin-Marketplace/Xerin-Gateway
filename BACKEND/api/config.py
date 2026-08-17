from __future__ import annotations

from pathlib import Path
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Xerin Marketplace API"
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
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000, http://169.58.54.110:8081, https://frontend-new-five-puce.vercel.app"
    TRUSTED_HOSTS: str = "localhost,127.0.0.1, http://169.58.54.110:8081"
    TRUST_PROXY_HEADERS: bool = False

    # Local uploads (temporary until object storage is introduced)
    UPLOAD_DIRECTORY: str = "uploads"
    SERVE_LOCAL_UPLOADS: bool = True
    MAX_UPLOAD_SIZE_MB: int = Field(default=5, ge=1)

    # Inventory reservations
    INVENTORY_RESERVATION_MINUTES: int = Field(default=30, ge=5, le=1440)
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
    EMAIL_FROM_NAME: str = "Xerin Market"
    EMAIL_REPLY_TO: str | None = None
    EMAIL_USE_TLS: bool = True
    EMAIL_USE_SSL: bool = False

    # SMS (Africa's Talking)
    AT_USERNAME: str | None = None
    AT_API_KEY: str | None = None
    AT_SENDER_ID: str | None = None
    SMS_DEFAULT_COUNTRY_CODE: str = "+255"
    SMS_API_URL: str | None = None

    # Payment webhook security
    PAYMENT_WEBHOOK_SECRET: str | None = None

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
    AZAMPAY_LIVE_AUTH_URL: str = "https://authenticator.azampay.co.tz/AppRegistration/GenerateToken"
    AZAMPAY_SANDBOX_BASE_URL: str = "https://sandbox.azampay.co.tz"
    AZAMPAY_LIVE_BASE_URL: str = "https://checkout.azampay.co.tz"
    AZAMPAY_MNO_CHECKOUT_PATH: str = "/azampay/mno/checkout"
    AZAMPAY_POST_CHECKOUT_PATH: str = "/azampay/checkout"
    AZAMPAY_NAME_LOOKUP_PATH: str = "/azampay/mno/lookup"
    AZAMPAY_PAYMENT_PARTNERS_PATH: str = "/api/v1/Partner/GetPaymentPartners"
    AZAMPAY_TIMEOUT_SECONDS: int = Field(default=30, ge=1, le=120)

    # External delivery provider
    DELIVERY_PROVIDER_NAME: str = "dependent-delivery"
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
