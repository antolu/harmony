from __future__ import annotations

import logging
import os

import redis
import redis.asyncio

from harmony.db.connection import get_async_pool
from harmony.db.repositories import ServiceConfigRepo

logger = logging.getLogger(__name__)

# Default for Docker deployments
DEFAULT_REDIS_URL = "redis://redis:6379/0"


async def _get_redis_url_from_db() -> str | None:
    pool = await get_async_pool()
    repo = ServiceConfigRepo(pool)
    config = await repo.get("redis_url")
    if config and config.is_configured:
        return config.value
    return None


async def get_async_redis() -> redis.asyncio.Redis:
    """Get Redis client with config from (in order):
    1. Environment variable REDIS_URL
    2. Database service_configs table
    3. Default value
    """
    # 1. Environment variable
    url = os.environ.get("REDIS_URL")
    if url:
        logger.debug(f"Connecting to Redis at {url} (from env)")
        return redis.asyncio.Redis.from_url(url, decode_responses=True)

    # 2. Database
    try:
        db_url = await _get_redis_url_from_db()
        if db_url:
            logger.debug(f"Connecting to Redis at {db_url} (from db)")
            return redis.asyncio.Redis.from_url(db_url, decode_responses=True)
    except Exception as e:
        logger.warning(f"Failed to fetch Redis config from DB: {e}")

    # 3. Default
    url = DEFAULT_REDIS_URL
    logger.debug(f"Connecting to Redis at {url} (default)")
    return redis.asyncio.Redis.from_url(url, decode_responses=True)


async def get_sync_redis() -> redis.Redis:
    """Get a synchronous Redis client, resolving the URL like get_async_redis.

    Used by call sites with a synchronous interface (e.g. RedisDocumentCache,
    whose get/set are called without await).
    """
    url = os.environ.get("REDIS_URL")
    if not url:
        try:
            url = await _get_redis_url_from_db()
        except Exception as e:
            logger.warning(f"Failed to fetch Redis config from DB: {e}")
            url = None
    url = url or DEFAULT_REDIS_URL
    return redis.Redis.from_url(url, decode_responses=True)
