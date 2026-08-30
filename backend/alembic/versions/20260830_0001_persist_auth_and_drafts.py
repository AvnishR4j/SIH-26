"""Persist authentication, profiles, OTP state, and catalogue drafts.

Revision ID: 20260830_0001
Revises:
Create Date: 2026-08-30 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "20260830_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "users",
    "otp_requests",
    "otp_attempts",
    "otp_idempotency",
    "catalog_drafts",
    "draft_create_idempotency",
)
JSON_DOCUMENT = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("phone", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("preferred_language", sa.String(length=8), nullable=False),
        sa.Column("cluster", sa.String(length=160), nullable=True),
        sa.Column("craft_categories", JSON_DOCUMENT, nullable=False),
        sa.Column("media_processing_accepted", sa.Boolean(), nullable=False),
        sa.Column("media_processing_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('artisan', 'facilitator', 'admin')",
            name=op.f("ck_users_role_allowed"),
        ),
        sa.CheckConstraint(
            "preferred_language IN ('hi', 'en')",
            name=op.f("ck_users_preferred_language_allowed"),
        ),
        sa.CheckConstraint(
            "(media_processing_accepted = true AND media_processing_accepted_at IS NOT NULL) "
            "OR (media_processing_accepted = false AND media_processing_accepted_at IS NULL)",
            name=op.f("ck_users_media_consent_consistent"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("phone", name=op.f("uq_users_phone")),
    )
    op.create_table(
        "otp_requests",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("phone", sa.String(length=16), nullable=False),
        sa.Column("otp_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_otp_requests")),
    )
    op.create_index("ix_otp_requests_phone_expires", "otp_requests", ["phone", "expires_at"])
    op.create_table(
        "otp_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("phone", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_otp_attempts")),
    )
    op.create_index("ix_otp_attempts_phone_created", "otp_attempts", ["phone", "created_at"])
    op.create_table(
        "otp_idempotency",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("phone", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("request_id", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_otp_idempotency")),
        sa.UniqueConstraint("phone", "idempotency_key", name=op.f("uq_otp_idempotency_phone")),
    )
    op.create_table(
        "catalog_drafts",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("owner_id", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", JSON_DOCUMENT, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version >= 1", name=op.f("ck_catalog_drafts_version_positive")),
        sa.CheckConstraint(
            "status IN ('draft', 'media_ready', 'processing', 'needs_confirmation', "
            "'ready_for_approval', 'approved', 'failed')",
            name=op.f("ck_catalog_drafts_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_catalog_drafts_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_drafts")),
    )
    op.create_index(
        "ix_catalog_drafts_owner_updated",
        "catalog_drafts",
        ["owner_id", "updated_at", "id"],
    )
    op.create_index(
        "ix_catalog_drafts_owner_status_updated",
        "catalog_drafts",
        ["owner_id", "status", "updated_at"],
    )
    op.create_table(
        "draft_create_idempotency",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("request_payload", JSON_DOCUMENT, nullable=False),
        sa.Column("draft_id", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["draft_id"],
            ["catalog_drafts.id"],
            name=op.f("fk_draft_create_idempotency_draft_id_catalog_drafts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_draft_create_idempotency_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_draft_create_idempotency")),
        sa.UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name=op.f("uq_draft_create_idempotency_owner_id"),
        ),
    )

    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_table("draft_create_idempotency")
    op.drop_index("ix_catalog_drafts_owner_status_updated", table_name="catalog_drafts")
    op.drop_index("ix_catalog_drafts_owner_updated", table_name="catalog_drafts")
    op.drop_table("catalog_drafts")
    op.drop_table("otp_idempotency")
    op.drop_index("ix_otp_attempts_phone_created", table_name="otp_attempts")
    op.drop_table("otp_attempts")
    op.drop_index("ix_otp_requests_phone_expires", table_name="otp_requests")
    op.drop_table("otp_requests")
    op.drop_table("users")
