from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://localhost:5432/cryptogo"
    redis_url: str = "redis://localhost:6379/0"
    telegram_bot_token: str | None = None
    telegram_auth_max_age_seconds: int = 43_200
    session_ttl_seconds: int = 86_400
    session_cookie_name: str = "cryptogo_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    dev_auth_enabled: bool = False
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    collect_radius_meters: int = 35
    max_location_accuracy_meters: int = 50
    max_client_location_age_seconds: int = 120

    @model_validator(mode="after")
    def production_requires_secure_configuration(self):
        if self.app_env == "production":
            if self.dev_auth_enabled:
                raise ValueError("Development authentication must be disabled in production")
            if not self.session_cookie_secure:
                raise ValueError("Production session cookies must use Secure")
            if self.session_cookie_samesite == "none" and not self.session_cookie_secure:
                raise ValueError("SameSite=None requires Secure cookies")
            if not self.telegram_bot_token:
                raise ValueError("TELEGRAM_BOT_TOKEN is required in production")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
