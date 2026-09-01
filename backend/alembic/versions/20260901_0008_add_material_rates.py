"""Store dated material rates for dynamic pricing.

Revision ID: 20260901_0008
Revises: 20260901_0007
Create Date: 2026-09-01 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260901_0008"
down_revision: str | Sequence[str] | None = "20260901_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "material_rates",
        sa.Column("material", sa.String(length=80), nullable=False),
        sa.Column("unit", sa.String(length=24), nullable=False),
        sa.Column("rate_paise_per_unit", sa.BigInteger(), nullable=False),
        sa.Column("source_label", sa.String(length=160), nullable=False),
        sa.Column("source_date", sa.Date(), nullable=False),
        sa.Column("is_demo_data", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "rate_paise_per_unit >= 0",
            name=op.f("ck_material_rates_rate_non_negative"),
        ),
        sa.PrimaryKeyConstraint("material", name=op.f("pk_material_rates")),
    )


def downgrade() -> None:
    op.drop_table("material_rates")
