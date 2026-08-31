"""Add durable media metadata, upload replays, and operations.

Revision ID: 20260830_0002
Revises: 20260830_0001
Create Date: 2026-08-30 01:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "20260830_0002"
down_revision: str | Sequence[str] | None = "20260830_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = sa.JSON().with_variant(JSONB, "postgresql")
NULLABLE_JSON_DOCUMENT = sa.JSON(none_as_null=True).with_variant(
    JSONB(none_as_null=True), "postgresql"
)
TABLES = (
    "media_objects",
    "image_upload_idempotency",
    "operations",
    "operation_idempotency",
)


def upgrade() -> None:
    op.add_column(
        "draft_create_idempotency",
        sa.Column("response_payload", NULLABLE_JSON_DOCUMENT, nullable=True),
    )
    op.create_table(
        "media_objects",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("owner_id", sa.String(length=32), nullable=False),
        sa.Column("draft_id", sa.String(length=40), nullable=False),
        sa.Column("original_key", sa.String(length=500), nullable=False),
        sa.Column("original_content_type", sa.String(length=40), nullable=False),
        sa.Column("original_size_bytes", sa.Integer(), nullable=False),
        sa.Column("original_sha256", sa.String(length=64), nullable=False),
        sa.Column("enhanced_key", sa.String(length=500), nullable=True),
        sa.Column("enhanced_content_type", sa.String(length=40), nullable=True),
        sa.Column("enhanced_size_bytes", sa.Integer(), nullable=True),
        sa.Column("enhanced_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "original_size_bytes > 0",
            name=op.f("ck_media_objects_original_size_positive"),
        ),
        sa.CheckConstraint(
            "(enhanced_key IS NULL AND enhanced_content_type IS NULL "
            "AND enhanced_size_bytes IS NULL AND enhanced_sha256 IS NULL) OR "
            "(enhanced_key IS NOT NULL AND enhanced_content_type IS NOT NULL "
            "AND enhanced_size_bytes > 0 AND enhanced_sha256 IS NOT NULL)",
            name=op.f("ck_media_objects_enhanced_metadata_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["draft_id"],
            ["catalog_drafts.id"],
            name=op.f("fk_media_objects_draft_id_catalog_drafts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_media_objects_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_objects")),
        sa.UniqueConstraint("enhanced_key", name=op.f("uq_media_objects_enhanced_key")),
        sa.UniqueConstraint("original_key", name=op.f("uq_media_objects_original_key")),
    )
    op.create_index(
        "ix_media_objects_draft_created",
        "media_objects",
        ["draft_id", "created_at", "id"],
    )
    op.create_table(
        "image_upload_idempotency",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_payload", JSON_DOCUMENT, nullable=False),
        sa.Column("image_id", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["image_id"],
            ["media_objects.id"],
            name=op.f("fk_image_upload_idempotency_image_id_media_objects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_image_upload_idempotency_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_image_upload_idempotency")),
        sa.UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name=op.f("uq_image_upload_idempotency_owner_id"),
        ),
    )
    op.create_table(
        "operations",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("owner_id", sa.String(length=32), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("resource_type", sa.String(length=20), nullable=False),
        sa.Column("resource_id", sa.String(length=40), nullable=False),
        sa.Column("internal_payload", JSON_DOCUMENT, nullable=False),
        sa.Column("error", NULLABLE_JSON_DOCUMENT, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type IN ('enhance_image', 'generate_listing')",
            name=op.f("ck_operations_type_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name=op.f("ck_operations_status_allowed"),
        ),
        sa.CheckConstraint(
            "resource_type = 'draft'", name=op.f("ck_operations_resource_type_allowed")
        ),
        sa.CheckConstraint(
            "(status = 'failed' AND error IS NOT NULL) OR (status != 'failed' AND error IS NULL)",
            name=op.f("ck_operations_error_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_operations_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["catalog_drafts.id"],
            name=op.f("fk_operations_resource_id_catalog_drafts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_operations")),
    )
    op.create_index("ix_operations_owner_updated", "operations", ["owner_id", "updated_at", "id"])
    op.create_table(
        "operation_idempotency",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.String(length=32), nullable=False),
        sa.Column("operation_type", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("request_payload", JSON_DOCUMENT, nullable=False),
        sa.Column("response_payload", JSON_DOCUMENT, nullable=False),
        sa.Column("operation_id", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operations.id"],
            name=op.f("fk_operation_idempotency_operation_id_operations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_operation_idempotency_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_operation_idempotency")),
        sa.UniqueConstraint(
            "owner_id",
            "operation_type",
            "idempotency_key",
            name=op.f("uq_operation_idempotency_owner_id"),
        ),
    )

    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_table("operation_idempotency")
    op.drop_index("ix_operations_owner_updated", table_name="operations")
    op.drop_table("operations")
    op.drop_table("image_upload_idempotency")
    op.drop_index("ix_media_objects_draft_created", table_name="media_objects")
    op.drop_table("media_objects")
    op.drop_column("draft_create_idempotency", "response_payload")
