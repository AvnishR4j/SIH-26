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
NULLABLE_JSON_DOCUMENT = JSON(none_as_null=True).with_variant(
    JSONB(none_as_null=True), "postgresql"
)


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
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(NULLABLE_JSON_DOCUMENT)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_drafts.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class MediaObject(Base):
    __tablename__ = "media_objects"
    __table_args__ = (
        CheckConstraint("original_size_bytes > 0", name="original_size_positive"),
        CheckConstraint(
            "(enhanced_key IS NULL AND enhanced_content_type IS NULL "
            "AND enhanced_size_bytes IS NULL AND enhanced_sha256 IS NULL) OR "
            "(enhanced_key IS NOT NULL AND enhanced_content_type IS NOT NULL "
            "AND enhanced_size_bytes > 0 AND enhanced_sha256 IS NOT NULL)",
            name="enhanced_metadata_consistent",
        ),
        Index("ix_media_objects_draft_created", "draft_id", "created_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_drafts.id", ondelete="CASCADE"), nullable=False
    )
    original_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    original_content_type: Mapped[str] = mapped_column(String(40), nullable=False)
    original_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    original_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    enhanced_key: Mapped[str | None] = mapped_column(String(500), unique=True)
    enhanced_content_type: Mapped[str | None] = mapped_column(String(40))
    enhanced_size_bytes: Mapped[int | None] = mapped_column(Integer)
    enhanced_sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class ImageUploadIdempotency(Base):
    __tablename__ = "image_upload_idempotency"
    __table_args__ = (UniqueConstraint("owner_id", "idempotency_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(36), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    image_id: Mapped[str] = mapped_column(
        ForeignKey("media_objects.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class Operation(Base):
    __tablename__ = "operations"
    __table_args__ = (
        CheckConstraint("type IN ('enhance_image', 'generate_listing')", name="type_allowed"),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="status_allowed",
        ),
        CheckConstraint("resource_type = 'draft'", name="resource_type_allowed"),
        CheckConstraint(
            "(status = 'failed' AND error IS NOT NULL) OR (status != 'failed' AND error IS NULL)",
            name="error_consistent",
        ),
        Index("ix_operations_owner_updated", "owner_id", "updated_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(20), nullable=False)
    resource_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_drafts.id", ondelete="CASCADE"), nullable=False
    )
    internal_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    error: Mapped[dict[str, Any] | None] = mapped_column(NULLABLE_JSON_DOCUMENT)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class OperationIdempotency(Base):
    __tablename__ = "operation_idempotency"
    __table_args__ = (UniqueConstraint("owner_id", "operation_type", "idempotency_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    operation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(36), nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    operation_id: Mapped[str] = mapped_column(
        ForeignKey("operations.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
