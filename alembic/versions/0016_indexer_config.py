from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "indexer_config",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
    )


def downgrade() -> None:
    op.drop_table("indexer_config")
