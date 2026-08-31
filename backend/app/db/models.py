from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
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


class VoiceMedia(Base):
    __tablename__ = "voice_media"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="size_positive"),
        CheckConstraint("duration_seconds BETWEEN 1 AND 120", name="duration_allowed"),
        CheckConstraint("language IN ('hi', 'en')", name="language_allowed"),
        Index("ix_voice_media_draft_created", "draft_id", "created_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_drafts.id", ondelete="CASCADE"), nullable=False
    )
    audio_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(40), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class VoiceUploadIdempotency(Base):
    __tablename__ = "voice_upload_idempotency"
    __table_args__ = (UniqueConstraint("owner_id", "idempotency_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(36), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    voice_id: Mapped[str] = mapped_column(
        ForeignKey("voice_media.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class PricingBenchmark(Base):
    __tablename__ = "pricing_benchmarks"
    __table_args__ = (
        CheckConstraint("low_paise >= 0", name="low_non_negative"),
        CheckConstraint("high_paise >= low_paise", name="range_allowed"),
    )

    category: Mapped[str] = mapped_column(String(80), primary_key=True)
    low_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    high_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_label: Mapped[str] = mapped_column(String(160), nullable=False)
    source_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_demo_data: Mapped[bool] = mapped_column(Boolean, nullable=False)


class PricingSuggestionIdempotency(Base):
    __tablename__ = "pricing_suggestion_idempotency"
    __table_args__ = (UniqueConstraint("owner_id", "idempotency_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(36), nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_drafts.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class CatalogSnapshot(Base):
    __tablename__ = "catalog_snapshots"
    __table_args__ = (
        CheckConstraint("approved_price_paise > 0", name="approved_price_positive"),
        CheckConstraint("source_draft_version >= 1", name="source_draft_version_positive"),
        UniqueConstraint("draft_id"),
        Index("ix_catalog_snapshots_owner_created", "owner_id", "created_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_drafts.id", ondelete="RESTRICT"), nullable=False
    )
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    public_share_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    public_image_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    source_draft_version: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price_override_reason: Mapped[str | None] = mapped_column(String(500))
    approval_note: Mapped[str | None] = mapped_column(String(1000))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ApprovalIdempotency(Base):
    __tablename__ = "approval_idempotency"
    __table_args__ = (UniqueConstraint("owner_id", "idempotency_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(36), nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    catalog_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class BuyerEnquiry(Base):
    __tablename__ = "buyer_enquiries"
    __table_args__ = (
        CheckConstraint(
            "quantity_requested IS NULL OR quantity_requested >= 1", name="quantity_allowed"
        ),
        CheckConstraint("consent_to_contact = true", name="contact_consent_required"),
        Index(
            "ix_buyer_enquiries_catalog_phone_created",
            "catalog_id",
            "buyer_phone",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    catalog_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    buyer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    buyer_phone: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str | None] = mapped_column(String(1000))
    quantity_requested: Mapped[int | None] = mapped_column(Integer)
    consent_to_contact: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class EnquiryIdempotency(Base):
    __tablename__ = "enquiry_idempotency"
    __table_args__ = (UniqueConstraint("public_share_id", "idempotency_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_share_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_snapshots.public_share_id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(36), nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    enquiry_id: Mapped[str] = mapped_column(
        ForeignKey("buyer_enquiries.id", ondelete="CASCADE"), nullable=False
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
