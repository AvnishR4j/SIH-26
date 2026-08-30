"""Add immutable catalogue snapshots and buyer enquiries.

Revision ID: 20260830_0005
Revises: 20260830_0004
Create Date: 2026-08-30 08:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "20260830_0005"
down_revision: str | Sequence[str] | None = "20260830_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = sa.JSON().with_variant(JSONB, "postgresql")
TABLES = (
    "catalog_snapshots",
    "approval_idempotency",
    "buyer_enquiries",
    "enquiry_idempotency",
)


def upgrade() -> None:
    op.create_table(
        "catalog_snapshots",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("draft_id", sa.String(length=40), nullable=False),
        sa.Column("owner_id", sa.String(length=32), nullable=False),
        sa.Column("public_share_id", sa.String(length=64), nullable=False),
        sa.Column("public_image_key", sa.String(length=500), nullable=False),
        sa.Column("source_draft_version", sa.Integer(), nullable=False),
        sa.Column("approved_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("price_override_reason", sa.String(length=500), nullable=True),
        sa.Column("approval_note", sa.String(length=1000), nullable=True),
        sa.Column("payload", JSON_DOCUMENT, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "approved_price_paise > 0",
            name=op.f("ck_catalog_snapshots_approved_price_positive"),
        ),
        sa.CheckConstraint(
            "source_draft_version >= 1",
            name=op.f("ck_catalog_snapshots_source_draft_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["draft_id"],
            ["catalog_drafts.id"],
            name=op.f("fk_catalog_snapshots_draft_id_catalog_drafts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_catalog_snapshots_owner_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_snapshots")),
        sa.UniqueConstraint("draft_id", name=op.f("uq_catalog_snapshots_draft_id")),
        sa.UniqueConstraint("public_share_id", name=op.f("uq_catalog_snapshots_public_share_id")),
        sa.UniqueConstraint("public_image_key", name=op.f("uq_catalog_snapshots_public_image_key")),
    )
    op.create_index(
        "ix_catalog_snapshots_owner_created",
        "catalog_snapshots",
        ["owner_id", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "approval_idempotency",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("request_payload", JSON_DOCUMENT, nullable=False),
        sa.Column("response_payload", JSON_DOCUMENT, nullable=False),
        sa.Column("catalog_id", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["catalog_id"],
            ["catalog_snapshots.id"],
            name=op.f("fk_approval_idempotency_catalog_id_catalog_snapshots"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_approval_idempotency_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval_idempotency")),
        sa.UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name=op.f("uq_approval_idempotency_owner_id"),
        ),
    )
    op.create_table(
        "buyer_enquiries",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("catalog_id", sa.String(length=40), nullable=False),
        sa.Column("buyer_name", sa.String(length=120), nullable=False),
        sa.Column("buyer_phone", sa.String(length=16), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=True),
        sa.Column("quantity_requested", sa.Integer(), nullable=True),
        sa.Column("consent_to_contact", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "quantity_requested IS NULL OR quantity_requested >= 1",
            name=op.f("ck_buyer_enquiries_quantity_allowed"),
        ),
        sa.CheckConstraint(
            "consent_to_contact = true",
            name=op.f("ck_buyer_enquiries_contact_consent_required"),
        ),
        sa.ForeignKeyConstraint(
            ["catalog_id"],
            ["catalog_snapshots.id"],
            name=op.f("fk_buyer_enquiries_catalog_id_catalog_snapshots"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_buyer_enquiries")),
    )
    op.create_index(
        "ix_buyer_enquiries_catalog_phone_created",
        "buyer_enquiries",
        ["catalog_id", "buyer_phone", "created_at"],
        unique=False,
    )
    op.create_table(
        "enquiry_idempotency",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("public_share_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("request_payload", JSON_DOCUMENT, nullable=False),
        sa.Column("response_payload", JSON_DOCUMENT, nullable=False),
        sa.Column("enquiry_id", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["public_share_id"],
            ["catalog_snapshots.public_share_id"],
            name=op.f("fk_enquiry_idempotency_public_share_id_catalog_snapshots"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["enquiry_id"],
            ["buyer_enquiries.id"],
            name=op.f("fk_enquiry_idempotency_enquiry_id_buyer_enquiries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_enquiry_idempotency")),
        sa.UniqueConstraint(
            "public_share_id",
            "idempotency_key",
            name=op.f("uq_enquiry_idempotency_public_share_id"),
        ),
    )

    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    op.drop_table("enquiry_idempotency")
    op.drop_index("ix_buyer_enquiries_catalog_phone_created", table_name="buyer_enquiries")
    op.drop_table("buyer_enquiries")
    op.drop_table("approval_idempotency")
    op.drop_index("ix_catalog_snapshots_owner_created", table_name="catalog_snapshots")
    op.drop_table("catalog_snapshots")
