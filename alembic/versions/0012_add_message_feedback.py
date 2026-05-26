"""add message_feedback table

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-26
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

down_revision = "0011"
revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "message_feedback",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            sa.Integer(),
            nullable=False,
            comment="Index into conversations.messages JSONB array",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column(
            "rating",
            sa.String(10),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "conversation_id",
            "message_id",
            "user_id",
            name="uq_feedback_conv_msg_user",
        ),
        sa.CheckConstraint(
            "rating IN ('up', 'down')", name="ck_message_feedback_rating"
        ),
    )
    op.create_index(
        "ix_message_feedback_user_id",
        "message_feedback",
        ["user_id"],
    )
    op.create_index(
        "ix_message_feedback_conversation_id",
        "message_feedback",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_table("message_feedback")
