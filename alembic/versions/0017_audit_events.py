from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=True),
        sa.Column(
            "details",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_audit_events_user_id_created_at",
        "audit_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_audit_events_action_created_at",
        "audit_events",
        ["action", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_action_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_user_id_created_at", table_name="audit_events")
    op.drop_table("audit_events")
