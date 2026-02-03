from __future__ import annotations

import os

import redis.asyncio


def get_async_redis() -> redis.asyncio.Redis:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return redis.asyncio.Redis.from_url(url, decode_responses=True)
