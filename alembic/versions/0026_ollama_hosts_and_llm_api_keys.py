"""ollama_hosts and llm_api_keys tables

Revision ID: 0026
Revises: 0025
Create Date: 2026-06-22
"""

from __future__ import annotations

import logging

import sqlalchemy as sa
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create table ollama_hosts
    op.create_table(
        "ollama_hosts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("host_type", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 2. Create table llm_api_keys
    op.create_table(
        "llm_api_keys",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("value_encrypted", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 3 & 4. Add columns and FKs to model_registry
    op.add_column(
        "model_registry",
        sa.Column("ollama_host_id", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.add_column(
        "model_registry",
        sa.Column("api_key_id", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.create_foreign_key(
        None,
        "model_registry",
        "ollama_hosts",
        ["ollama_host_id"],
        ["id"],
    )
    op.create_foreign_key(
        None,
        "model_registry",
        "llm_api_keys",
        ["api_key_id"],
        ["id"],
    )

    # 5. Backfill ollama_hosts and ollama_host_id
    conn = op.get_bind()
    distinct_hosts = conn.execute(
        sa.text(
            "SELECT DISTINCT ollama_host FROM model_registry WHERE ollama_host IS NOT NULL AND ollama_host != ''"
        )
    ).fetchall()
    for i, (host_url,) in enumerate(distinct_hosts, start=1):
        result = conn.execute(
            sa.text(
                "INSERT INTO ollama_hosts (name, url, host_type) VALUES (:name, :url, 'ollama') RETURNING id"
            ),
            {"name": f"Migrated host {i}", "url": host_url},
        )
        new_id = result.fetchone()[0]
        conn.execute(
            sa.text(
                "UPDATE model_registry SET ollama_host_id = :id WHERE ollama_host = :url"
            ),
            {"id": new_id, "url": host_url},
        )

    # 6. Backfill llm_api_keys and api_key_id
    secret_key = conn.execute(
        sa.text("SELECT value FROM service_configs WHERE key = 'harmony_secret_key'")
    ).scalar()

    if secret_key:
        fernet = Fernet(secret_key.encode())
        rows = conn.execute(
            sa.text(
                "SELECT id, api_key_encrypted FROM model_registry WHERE api_key_encrypted IS NOT NULL AND api_key_encrypted != ''"
            )
        ).fetchall()

        plaintext_to_new_id: dict[str, str] = {}
        for model_pk, ciphertext in rows:
            try:
                plaintext = fernet.decrypt(ciphertext.encode()).decode()
            except InvalidToken:
                logging.warning(
                    f"Could not decrypt api_key_encrypted for model {model_pk}"
                )
                continue

            if plaintext not in plaintext_to_new_id:
                result = conn.execute(
                    sa.text(
                        "INSERT INTO llm_api_keys (name, value_encrypted) VALUES (:name, :enc) RETURNING id"
                    ),
                    {
                        "name": f"Migrated key {len(plaintext_to_new_id) + 1}",
                        "enc": ciphertext,
                    },
                )
                plaintext_to_new_id[plaintext] = result.fetchone()[0]

            conn.execute(
                sa.text(
                    "UPDATE model_registry SET api_key_id = :id WHERE id = :model_pk"
                ),
                {"id": plaintext_to_new_id[plaintext], "model_pk": model_pk},
            )

    # 7. Drop columns model_registry.ollama_host and model_registry.api_key_encrypted
    op.drop_column("model_registry", "ollama_host")
    op.drop_column("model_registry", "api_key_encrypted")


def downgrade() -> None:
    # Reverse of upgrade
    op.add_column(
        "model_registry",
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "model_registry",
        sa.Column("ollama_host", sa.Text(), nullable=True),
    )

    # In downgrade we should drop the FKs and then the columns.
    # Since we passed `None` to constraint name we can just drop by column which usually works
    # but dropping columns drops dependent constraints in Postgres if we use cascade, or alembic might need names.
    # We will just drop columns and rely on that. Or we can drop constraints by name if we named them.
    # Alembic drop_column usually works fine. Actually alembic needs drop_constraint with explicit names.
    # Better yet, I should not drop constraints if dropping the table/columns drops them implicitly,
    # but for model_registry we are dropping columns `ollama_host_id` and `api_key_id`

    op.drop_constraint(
        "model_registry_api_key_id_fkey", "model_registry", type_="foreignkey"
    )
    op.drop_constraint(
        "model_registry_ollama_host_id_fkey", "model_registry", type_="foreignkey"
    )

    op.drop_column("model_registry", "api_key_id")
    op.drop_column("model_registry", "ollama_host_id")

    op.drop_table("llm_api_keys")
    op.drop_table("ollama_hosts")
