from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
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
    public_api_base_url: str = "http://localhost:8000"
    public_share_web_base_url: str = "http://localhost:3000"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8080"]
    )
    jwt_secret: str = "development-only-secret-change-before-production"
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_expires_seconds: int = 86400
    otp_expires_seconds: int = 300
    otp_retry_after_seconds: int = 30
    otp_max_requests_per_15_minutes: int = 5
    otp_idempotency_ttl_seconds: int = 60
    idempotency_ttl_seconds: int = 86400
    enquiry_max_per_hour_per_buyer: int = Field(default=5, ge=1, le=100)
    dev_otp: str | None = "123456"
    media_consent_policy_version: str = "2026-08-29"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/kalasetu"
    database_echo: bool = False
    database_auto_create: bool = False
    media_storage: Literal["local"] = "local"
    media_local_dir: Path = Path("./media")
    media_url_base: str = "http://localhost:8000/media"
    max_image_bytes: int = Field(default=10_485_760, ge=1)
    max_image_pixels: int = Field(default=25_000_000, ge=1)
    max_audio_bytes: int = Field(default=26_214_400, ge=1)
    max_audio_duration_seconds: int = Field(default=120, ge=1, le=120)
    ai_operation_poll_after_seconds: int = Field(default=2, ge=1, le=60)
    image_enhancement_provider: Literal["mock"] = "mock"
    speech_provider: Literal["faster_whisper"] = "faster_whisper"
    whisper_model_size: str = "small"
    whisper_device: Literal["cpu", "cuda"] = "cpu"
    whisper_compute_type: str = "int8"
    whisper_cpu_threads: int = Field(default=4, ge=1, le=64)
    whisper_model_cache_dir: Path = Path("./models/faster-whisper")

    @field_validator("whisper_model_size", "whisper_compute_type")
    @classmethod
    def reject_blank_whisper_setting(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Whisper model settings cannot be blank")
        return cleaned

    @field_validator("media_url_base")
    @classmethod
    def validate_media_url_base(cls, value: str) -> str:
        normalized = value.rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("MEDIA_URL_BASE must be an absolute HTTP(S) URL")
        return normalized

    @field_validator("public_api_base_url", "public_share_web_base_url")
    @classmethod
    def validate_public_url(cls, value: str) -> str:
        normalized = value.rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("Public URLs must be absolute HTTP(S) URLs")
        return normalized

    @model_validator(mode="after")
    def reject_development_secrets_in_production(self) -> "Settings":
        if self.environment == "production" and self.dev_otp is not None:
            raise ValueError("DEV_OTP must be unset in production")
        if self.environment == "production" and (
            "development-only" in self.jwt_secret or "CHANGE_ME" in self.jwt_secret
        ):
            raise ValueError("JWT_SECRET must be replaced in production")
        if self.environment == "production" and len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters in production")
        if self.environment == "production" and self.database_auto_create:
            raise ValueError(
                "DATABASE_AUTO_CREATE must be false in production; run migrations instead"
            )
        if self.environment == "production" and not self.media_url_base.startswith("https://"):
            raise ValueError("MEDIA_URL_BASE must use HTTPS in production")
        if self.environment == "production" and not self.public_share_web_base_url.startswith(
            "https://"
        ):
            raise ValueError("PUBLIC_SHARE_WEB_BASE_URL must use HTTPS in production")
        if self.environment == "production" and not self.public_api_base_url.startswith("https://"):
            raise ValueError("PUBLIC_API_BASE_URL must use HTTPS in production")
        if self.environment == "production" and any(
            not origin.startswith("https://") for origin in self.cors_origins
        ):
            raise ValueError("CORS_ORIGINS must use HTTPS in production")
        if self.environment == "production" and self.media_storage == "local":
            raise ValueError(
                "MEDIA_STORAGE=local is development-only; configure private object storage"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
