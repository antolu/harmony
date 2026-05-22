"""add harmony_role to api_keys (create table if missing)

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
    conn = op.get_bind()
    table_exists = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'api_keys'"
        )
    ).fetchone()

    if not table_exists:
        op.create_table(
            "api_keys",
            sa.Column("key", sa.Text(), primary_key=True),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column(
                "harmony_role",
                sa.String(64),
                nullable=False,
                server_default="service",
            ),
        )
    else:
        col_exists = conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'api_keys' AND column_name = 'harmony_role'"
            )
        ).fetchone()
        if not col_exists:
            op.add_column(
                "api_keys",
                sa.Column(
                    "harmony_role",
                    sa.String(64),
                    server_default="service",
                    nullable=False,
                ),
            )


def downgrade() -> None:
    op.drop_column("api_keys", "harmony_role")
