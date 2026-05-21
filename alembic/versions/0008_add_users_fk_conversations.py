"""add users FK to conversations

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-21
"""

from __future__ import annotations

from alembic import op

down_revision = "0007"
revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
