"""Add reversible catalogue visibility controls.

Revision ID: 20260901_0006
Revises: 20260830_0005
Create Date: 2026-09-01 19:15:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260901_0006"
down_revision: str | Sequence[str] | None = "20260830_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "catalog_drafts",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "catalog_snapshots",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("catalog_snapshots", "is_deleted")
    op.drop_column("catalog_drafts", "is_deleted")
