from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utc_now

JSON_DOCUMENT = JSON().with_variant(JSONB, "postgresql")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('artisan', 'facilitator', 'admin')", name="role_allowed"),
        CheckConstraint("preferred_language IN ('hi', 'en')", name="preferred_language_allowed"),
        CheckConstraint(
            "(media_processing_accepted = true AND media_processing_accepted_at IS NOT NULL) "
            "OR (media_processing_accepted = false AND media_processing_accepted_at IS NULL)",
            name="media_consent_consistent",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    phone: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="Artisan")
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="artisan")
    preferred_language: Mapped[str] = mapped_column(String(8), nullable=False, default="hi")
    cluster: Mapped[str | None] = mapped_column(String(160))
    craft_categories: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False, default=list)
    media_processing_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    media_processing_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class OtpRequest(Base):
    __tablename__ = "otp_requests"
    __table_args__ = (Index("ix_otp_requests_phone_expires", "phone", "expires_at"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    phone: Mapped[str] = mapped_column(String(16), nullable=False)
    otp_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class OtpAttempt(Base):
    __tablename__ = "otp_attempts"
    __table_args__ = (Index("ix_otp_attempts_phone_created", "phone", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class OtpIdempotency(Base):
    __tablename__ = "otp_idempotency"
    __table_args__ = (UniqueConstraint("phone", "idempotency_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(36), nullable=False)
    request_id: Mapped[str] = mapped_column(String(40), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class CatalogDraft(Base):
    __tablename__ = "catalog_drafts"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "status IN ('draft', 'media_ready', 'processing', 'needs_confirmation', "
            "'ready_for_approval', 'approved', 'failed')",
            name="status_allowed",
        ),
        Index("ix_catalog_drafts_owner_updated", "owner_id", "updated_at", "id"),
        Index("ix_catalog_drafts_owner_status_updated", "owner_id", "status", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DraftCreateIdempotency(Base):
    __tablename__ = "draft_create_idempotency"
    __table_args__ = (UniqueConstraint("owner_id", "idempotency_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(36), nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_drafts.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
