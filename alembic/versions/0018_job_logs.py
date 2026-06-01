from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_job_logs_job_id", "job_logs", ["job_id"])
    op.create_index("ix_job_logs_created_at", "job_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_job_logs_created_at", table_name="job_logs")
    op.drop_index("ix_job_logs_job_id", table_name="job_logs")
    op.drop_table("job_logs")
