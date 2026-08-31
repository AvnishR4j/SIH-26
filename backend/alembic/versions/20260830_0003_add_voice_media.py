"""Add durable voice media and upload replay metadata.

Revision ID: 20260830_0003
Revises: 20260830_0002
Create Date: 2026-08-30 03:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "20260830_0003"
down_revision: str | Sequence[str] | None = "20260830_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = sa.JSON().with_variant(JSONB, "postgresql")
TABLES = ("voice_media", "voice_upload_idempotency")


def upgrade() -> None:
    op.create_table(
        "voice_media",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("owner_id", sa.String(length=32), nullable=False),
        sa.Column("draft_id", sa.String(length=40), nullable=False),
        sa.Column("audio_key", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=40), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_voice_media_size_positive")),
        sa.CheckConstraint(
            "duration_seconds BETWEEN 1 AND 120",
            name=op.f("ck_voice_media_duration_allowed"),
        ),
        sa.CheckConstraint(
            "language IN ('hi', 'en')", name=op.f("ck_voice_media_language_allowed")
        ),
        sa.ForeignKeyConstraint(
            ["draft_id"],
            ["catalog_drafts.id"],
            name=op.f("fk_voice_media_draft_id_catalog_drafts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_voice_media_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_voice_media")),
        sa.UniqueConstraint("audio_key", name=op.f("uq_voice_media_audio_key")),
    )
    op.create_index(
        "ix_voice_media_draft_created",
        "voice_media",
        ["draft_id", "created_at", "id"],
    )
    op.create_table(
        "voice_upload_idempotency",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_payload", JSON_DOCUMENT, nullable=False),
        sa.Column("voice_id", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_voice_upload_idempotency_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["voice_id"],
            ["voice_media.id"],
            name=op.f("fk_voice_upload_idempotency_voice_id_voice_media"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_voice_upload_idempotency")),
        sa.UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name=op.f("uq_voice_upload_idempotency_owner_id"),
        ),
    )

    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_table("voice_upload_idempotency")
    op.drop_index("ix_voice_media_draft_created", table_name="voice_media")
    op.drop_table("voice_media")
