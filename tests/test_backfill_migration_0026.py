from __future__ import annotations

import os
import subprocess
import typing

import psycopg
import pytest
from cryptography.fernet import Fernet

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


@pytest.fixture
def db_url() -> str:
    return os.environ.get(
        "DATABASE_URL", "postgresql://harmony:harmony@localhost:5432/harmony"
    )


@pytest.fixture(autouse=True)
def setup_db(db_url: str) -> typing.Generator[None, None, None]:
    subprocess.run(["alembic", "downgrade", "0025"], check=False, capture_output=True)
    yield
    subprocess.run(["alembic", "upgrade", "head"], check=False, capture_output=True)


async def test_backfill_dedup_migration(db_url: str) -> None:
    subprocess.run(["alembic", "downgrade", "0025"], check=True, capture_output=True)

    async with (
        await psycopg.AsyncConnection.connect(db_url) as conn,
        conn.cursor() as cur,
    ):
        await conn.set_autocommit(True)
        await cur.execute("DELETE FROM model_registry")

        fernet_key = Fernet.generate_key()
        await cur.execute(
            "DELETE FROM service_configs WHERE key = 'harmony_secret_key'"
        )
        await cur.execute(
            "INSERT INTO service_configs (key, value) VALUES ('harmony_secret_key', %s)",
            (fernet_key.decode(),),
        )

        f = Fernet(fernet_key)
        plaintext_key = "sk-test-identical-plaintext"

        ciphertext1 = f.encrypt(plaintext_key.encode()).decode()
        ciphertext2 = f.encrypt(plaintext_key.encode()).decode()

        assert ciphertext1 != ciphertext2

        await cur.execute(
            """
            INSERT INTO model_registry
            (name, provider, model_id, model_type, api_key_encrypted, ollama_host)
            VALUES
            ('model1', 'ollama', 'model1', 'llm', %s, 'http://duplicate-host'),
            ('model2', 'ollama', 'model2', 'llm', %s, 'http://duplicate-host')
            """,
            (ciphertext1, ciphertext2),
        )

    subprocess.run(["alembic", "upgrade", "0026"], check=True, capture_output=True)

    async with (
        await psycopg.AsyncConnection.connect(db_url) as conn,
        conn.cursor() as cur,
    ):
        await cur.execute(
            "SELECT id FROM ollama_hosts WHERE url = 'http://duplicate-host'"
        )
        host_rows = await cur.fetchall()
        assert len(host_rows) == 1
        host_id = host_rows[0][0]

        await cur.execute(
            "SELECT ollama_host_id, api_key_id FROM model_registry "
            "WHERE name IN ('model1', 'model2') ORDER BY name"
        )
        registry_rows = await cur.fetchall()
        assert len(registry_rows) == 2

        m1_host, m1_key = registry_rows[0]
        m2_host, m2_key = registry_rows[1]

        assert str(m1_host) == str(host_id)
        assert str(m2_host) == str(host_id)

        assert m1_key is not None
        assert str(m1_key) == str(m2_key)

        await cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'model_registry'"
        )
        columns = {row[0] for row in await cur.fetchall()}
        assert "ollama_host" not in columns
        assert "api_key_encrypted" not in columns
