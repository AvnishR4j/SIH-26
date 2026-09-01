"""Track Shopify products created from approved catalogues.

Revision ID: 20260901_0007
Revises: 20260901_0006
Create Date: 2026-09-01 21:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260901_0007"
down_revision: str | Sequence[str] | None = "20260901_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("catalog_snapshots") as batch:
        batch.add_column(sa.Column("shopify_product_id", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("shopify_product_handle", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("shopify_synced_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_unique_constraint(
            "uq_catalog_snapshots_shopify_product_id", ["shopify_product_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("catalog_snapshots") as batch:
        batch.drop_constraint("uq_catalog_snapshots_shopify_product_id", type_="unique")
        batch.drop_column("shopify_synced_at")
        batch.drop_column("shopify_product_handle")
        batch.drop_column("shopify_product_id")
