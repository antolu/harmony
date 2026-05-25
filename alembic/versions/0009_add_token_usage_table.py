"""add token_usage and model_policy tables

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-22
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

down_revision = "0008"
revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "token_usage",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.Text, nullable=True),
        sa.Column("user_id", sa.Text, nullable=True),
        sa.Column("endpoint", sa.Text, nullable=True),
        sa.Column("agent_step", sa.Text, nullable=True),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("provider", sa.Text, nullable=True),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("total_tokens", sa.Integer, nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "model_policy",
        sa.Column("model_id", sa.Text, primary_key=True),
        sa.Column("harmony_role", sa.Text, primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("token_usage")
    op.drop_table("model_policy")
