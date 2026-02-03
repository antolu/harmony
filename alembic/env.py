from __future__ import annotations

import os

from sqlalchemy import create_engine

from alembic import context

url = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/harmony")
# psycopg is the default driver for postgresql:// in SQLAlchemy 2.0
engine = create_engine(url)


def run_migrations_online() -> None:
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(url=url, target_metadata=None, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
