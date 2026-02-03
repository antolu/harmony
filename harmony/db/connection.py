from __future__ import annotations

import os

import psycopg_pool

_async_pool: psycopg_pool.AsyncConnectionPool | None = None


async def get_async_pool() -> psycopg_pool.AsyncConnectionPool:
    global _async_pool  # noqa: PLW0603
    if _async_pool is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            msg = "DATABASE_URL environment variable is not set"
            raise RuntimeError(msg)
        _async_pool = psycopg_pool.AsyncConnectionPool(
            conninfo=url, min_size=2, max_size=10, open=False
        )
        await _async_pool.open()
    return _async_pool


async def close_async_pool() -> None:
    global _async_pool  # noqa: PLW0603
    if _async_pool is not None:
        await _async_pool.close()
        _async_pool = None
