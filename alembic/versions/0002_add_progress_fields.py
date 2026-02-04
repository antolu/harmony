"""add progress_total_documents and progress_current_phase columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-04
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

down_revision = "0001"
revision = "0002"
branch_labels = None
depends = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "progress_total_documents", sa.Integer, nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "jobs",
        sa.Column("progress_current_phase", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "progress_current_phase")
    op.drop_column("jobs", "progress_total_documents")
