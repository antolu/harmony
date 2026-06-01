from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "indexer_checkpoints",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("config_name", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "indexed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "config_name",
            "url",
            name="uq_indexer_checkpoints_config_url",
        ),
    )
    op.create_index(
        "ix_indexer_checkpoints_config_name",
        "indexer_checkpoints",
        ["config_name"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_indexer_checkpoints_config_name", table_name="indexer_checkpoints"
    )
    op.drop_table("indexer_checkpoints")
