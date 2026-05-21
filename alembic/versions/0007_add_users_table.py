"""add users table

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-21
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

down_revision = "0006"
revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    harmony_role = postgresql.ENUM(
        "admin", "operator", "read_only", name="harmony_role"
    )
    harmony_role.create(op.get_bind())

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("sub", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column(
            "harmony_role",
            postgresql.ENUM(
                "admin", "operator", "read_only", name="harmony_role", create_type=False
            ),
            nullable=False,
            server_default="read_only",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_users_sub", "users", ["sub"], unique=True)
    op.create_index("ix_users_created_at", "users", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_users_created_at", table_name="users")
    op.drop_index("ix_users_sub", table_name="users")
    op.drop_table("users")
    postgresql.ENUM(name="harmony_role").drop(op.get_bind())
