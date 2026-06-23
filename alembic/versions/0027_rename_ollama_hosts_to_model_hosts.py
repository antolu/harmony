"""rename ollama_hosts to model_hosts

Revision ID: 0027
Revises: 0026
Create Date: 2026-06-23
"""

from __future__ import annotations

from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("ollama_hosts", "model_hosts")
    op.alter_column("model_registry", "ollama_host_id", new_column_name="model_host_id")
    op.execute(
        "ALTER TABLE model_registry "
        "RENAME CONSTRAINT model_registry_ollama_host_id_fkey "
        "TO model_registry_model_host_id_fkey"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE model_registry "
        "RENAME CONSTRAINT model_registry_model_host_id_fkey "
        "TO model_registry_ollama_host_id_fkey"
    )
    op.alter_column("model_registry", "model_host_id", new_column_name="ollama_host_id")
    op.rename_table("model_hosts", "ollama_hosts")
