"""initial tables: safety_lists, auth_sessions, jobs

Revision ID: 0001
Revises:
Create Date: 2026-02-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

down_revision = None
revision = "0001"
branch_labels = None
depends = None


def upgrade() -> None:
    op.create_table(
        "safety_lists",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("pattern", sa.Text, nullable=False),
        sa.Column("list_type", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("list_type IN ('allow', 'deny')", name="ck_safety_lists_list_type"),
    )
    op.create_index("uq_safety_pattern_type", "safety_lists", ["pattern", "list_type"], unique=True)

    op.create_table(
        "auth_sessions",
        sa.Column("subdomain", sa.Text, primary_key=True),
        sa.Column("provider_type", sa.Text, nullable=False),
        sa.Column("domain_pattern", sa.Text, nullable=False, server_default=""),
        sa.Column("cookies", JSONB, nullable=False, server_default="{}"),
        sa.Column("headers", JSONB, nullable=False, server_default="{}"),
        sa.Column("storage_state_file", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("config_name", sa.Text, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pid", sa.Integer, nullable=True),
        sa.Column("log_file", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("progress_pages_crawled", sa.Integer, nullable=False, server_default="0"),
        sa.Column("progress_pages_pending", sa.Integer, nullable=False, server_default="0"),
        sa.Column("progress_requests_made", sa.Integer, nullable=False, server_default="0"),
        sa.Column("progress_pages_per_min", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("progress_current_url", sa.Text, nullable=True),
        sa.Column("progress_documents_indexed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("progress_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("type IN ('crawl', 'index')", name="ck_jobs_type"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'paused', 'completed', 'failed', 'stopped')",
            name="ck_jobs_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_table("auth_sessions")
    op.drop_index("uq_safety_pattern_type", table_name="safety_lists")
    op.drop_table("safety_lists")
