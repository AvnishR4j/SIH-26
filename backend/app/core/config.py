from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "KalaSetu API"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8080"]
    )
    jwt_secret: str = "development-only-secret-change-before-production"
    jwt_algorithm: str = "HS256"
    jwt_expires_seconds: int = 86400
    otp_expires_seconds: int = 300
    otp_retry_after_seconds: int = 30
    otp_max_requests_per_15_minutes: int = 5
    otp_idempotency_ttl_seconds: int = 60
    dev_otp: str | None = "123456"
    media_consent_policy_version: str = "2026-08-29"

    @model_validator(mode="after")
    def reject_development_secrets_in_production(self) -> "Settings":
        if self.environment == "production" and self.dev_otp is not None:
            raise ValueError("DEV_OTP must be unset in production")
        if self.environment == "production" and (
            "development-only" in self.jwt_secret or "CHANGE_ME" in self.jwt_secret
        ):
            raise ValueError("JWT_SECRET must be replaced in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
