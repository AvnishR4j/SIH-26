"""Add pricing benchmarks and durable suggestion replays.

Revision ID: 20260830_0004
Revises: 20260830_0003
Create Date: 2026-08-30 05:00:00
"""

from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "20260830_0004"
down_revision: str | Sequence[str] | None = "20260830_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = sa.JSON().with_variant(JSONB, "postgresql")
TABLES = ("pricing_benchmarks", "pricing_suggestion_idempotency")


def upgrade() -> None:
    benchmarks = op.create_table(
        "pricing_benchmarks",
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("low_paise", sa.BigInteger(), nullable=False),
        sa.Column("high_paise", sa.BigInteger(), nullable=False),
        sa.Column("source_label", sa.String(length=160), nullable=False),
        sa.Column("source_date", sa.Date(), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.CheckConstraint("low_paise >= 0", name=op.f("ck_pricing_benchmarks_low_non_negative")),
        sa.CheckConstraint(
            "high_paise >= low_paise", name=op.f("ck_pricing_benchmarks_range_allowed")
        ),
        sa.PrimaryKeyConstraint("category", name=op.f("pk_pricing_benchmarks")),
    )
    op.bulk_insert(
        benchmarks,
        [
            {
                "category": "cotton_dupatta",
                "low_paise": 80_000,
                "high_paise": 140_000,
                "source_label": "Demo benchmark dataset",
                "source_date": date(2026, 8, 29),
                "is_demo_data": True,
            },
            {
                "category": "chikankari_textile",
                "low_paise": 100_000,
                "high_paise": 250_000,
                "source_label": "Demo benchmark dataset",
                "source_date": date(2026, 8, 29),
                "is_demo_data": True,
            },
            {
                "category": "handmade_pottery",
                "low_paise": 50_000,
                "high_paise": 180_000,
                "source_label": "Demo benchmark dataset",
                "source_date": date(2026, 8, 29),
                "is_demo_data": True,
            },
            {
                "category": "generic_handicraft",
                "low_paise": 50_000,
                "high_paise": 200_000,
                "source_label": "Demo benchmark dataset",
                "source_date": date(2026, 8, 29),
                "is_demo_data": True,
            },
        ],
    )
    op.create_table(
        "pricing_suggestion_idempotency",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("request_payload", JSON_DOCUMENT, nullable=False),
        sa.Column("response_payload", JSON_DOCUMENT, nullable=False),
        sa.Column("draft_id", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["draft_id"],
            ["catalog_drafts.id"],
            name=op.f("fk_pricing_suggestion_idempotency_draft_id_catalog_drafts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_pricing_suggestion_idempotency_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pricing_suggestion_idempotency")),
        sa.UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name=op.f("uq_pricing_suggestion_idempotency_owner_id"),
        ),
    )

    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(
            'CREATE POLICY "pricing_benchmarks_read" ON "pricing_benchmarks" '
            "FOR SELECT USING (true)"
        )


def downgrade() -> None:
    op.drop_table("pricing_suggestion_idempotency")
    op.drop_table("pricing_benchmarks")
