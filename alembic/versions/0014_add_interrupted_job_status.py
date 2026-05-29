from __future__ import annotations

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE jobs DROP CONSTRAINT ck_jobs_status")
    op.execute(
        "ALTER TABLE jobs ADD CONSTRAINT ck_jobs_status CHECK ("
        "status IN ('pending', 'running', 'paused', 'completed', 'failed', 'stopped', 'interrupted')"
        ")"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE jobs DROP CONSTRAINT ck_jobs_status")
    op.execute(
        "ALTER TABLE jobs ADD CONSTRAINT ck_jobs_status CHECK ("
        "status IN ('pending', 'running', 'paused', 'completed', 'failed', 'stopped')"
        ")"
    )
