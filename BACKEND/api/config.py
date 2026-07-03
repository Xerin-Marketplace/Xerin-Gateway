from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DEBUG: bool = False

    REDIS_URL: str | None = None

    # email settings
    EMAIL_HOST: str | None = None
    EMAIL_PORT: int = 587
    EMAIL_USER: str | None = None
    EMAIL_PASSWORD: str | None = None
    EMAIL_FROM: str | None = None
    EMAIL_USE_TLS: bool = True
    EMAIL_USE_SSL: bool = False

    # sms settings (Africa's Talking)
    AT_USERNAME: str | None = None
    AT_API_KEY: str | None = None
    AT_SENDER_ID: str | None = None
    SMS_API_URL: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()