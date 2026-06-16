from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crawl_blacklist",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("pattern", name="uq_crawl_blacklist_pattern"),
    )
    op.create_index("ix_crawl_blacklist_pattern", "crawl_blacklist", ["pattern"])


def downgrade() -> None:
    op.drop_index("ix_crawl_blacklist_pattern", table_name="crawl_blacklist")
    op.drop_table("crawl_blacklist")
