"""add users FK to conversations

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-21
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

down_revision = "0007"
revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "conversations",
        "user_id",
        type_=postgresql.UUID(as_uuid=False),
        postgresql_using="user_id::uuid",
        nullable=True,
    )
    op.create_foreign_key(
        "fk_conversations_user_id",
        "conversations",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_conversations_user_id", "conversations", type_="foreignkey")
    op.alter_column(
        "conversations",
        "user_id",
        type_=sa.Text(),
        postgresql_using="user_id::text",
        nullable=True,
    )
