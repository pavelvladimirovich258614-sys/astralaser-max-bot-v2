"""drop max_photo_id keep only token

Revision ID: 757c0c6d689a
Revises: df15104d0e4b
Create Date: 2026-05-08 01:21:52.417726

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "757c0c6d689a"
down_revision: str | None = "df15104d0e4b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite does not support ALTER COLUMN; use batch_alter_table
    with op.batch_alter_table("product_photos") as batch_op:
        batch_op.alter_column(
            "max_photo_token",
            existing_type=sa.VARCHAR(length=128),
            type_=sa.String(length=512),
            existing_nullable=True,
        )
        batch_op.drop_column("max_photo_id")


def downgrade() -> None:
    with op.batch_alter_table("product_photos") as batch_op:
        batch_op.add_column(sa.Column("max_photo_id", sa.INTEGER(), nullable=True))
        batch_op.alter_column(
            "max_photo_token",
            existing_type=sa.String(length=512),
            type_=sa.VARCHAR(length=128),
            existing_nullable=True,
        )
