"""add_user_max_chat_id

Revision ID: 98f27f674c26
Revises: 757c0c6d689a
Create Date: 2026-05-12 21:28:40.555796

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '98f27f674c26'
down_revision: str | None = '757c0c6d689a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("max_chat_id", sa.String(length=64), nullable=True))
    op.create_index("ix_users_max_chat_id", "users", ["max_chat_id"])


def downgrade() -> None:
    op.drop_index("ix_users_max_chat_id", table_name="users")
    op.drop_column("users", "max_chat_id")
