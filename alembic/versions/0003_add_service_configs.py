"""add service_configs table

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-04
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

down_revision = "0002"
revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_configs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(255), unique=True, nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_configured", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # Create index on key for faster lookups
    op.create_index("ix_service_configs_key", "service_configs", ["key"])


def downgrade() -> None:
    op.drop_index("ix_service_configs_key", table_name="service_configs")
    op.drop_table("service_configs")
