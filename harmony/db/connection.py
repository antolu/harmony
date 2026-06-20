from __future__ import annotations

import os

import psycopg_pool


class _PoolHolder:
    pool: psycopg_pool.AsyncConnectionPool | None = None


_pool_holder = _PoolHolder()


async def get_async_pool() -> psycopg_pool.AsyncConnectionPool:
    if _pool_holder.pool is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            msg = "DATABASE_URL environment variable is not set"
            raise RuntimeError(msg)
        _pool_holder.pool = psycopg_pool.AsyncConnectionPool(
            conninfo=url, min_size=2, max_size=10, open=False
        )
        await _pool_holder.pool.open()
    return _pool_holder.pool


async def close_async_pool() -> None:
    if _pool_holder.pool is not None:
        await _pool_holder.pool.close()
        _pool_holder.pool = None
