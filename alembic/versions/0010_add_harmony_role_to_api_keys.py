"""add harmony_role to api_keys

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-22
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

down_revision = "0009"
revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column(
            "harmony_role", sa.String(64), server_default="service", nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "harmony_role")
