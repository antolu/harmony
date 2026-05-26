"""add mode and title columns to conversations

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

down_revision = "0010"
revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "mode",
            sa.String(50),
            nullable=False,
            server_default="search",
        ),
    )
    op.add_column(
        "conversations",
        sa.Column("title", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_conversations_user_updated",
        "conversations",
        ["user_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_user_updated", table_name="conversations")
    op.drop_column("conversations", "title")
    op.drop_column("conversations", "mode")
