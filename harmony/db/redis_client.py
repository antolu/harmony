from __future__ import annotations

import logging
import os

import redis.asyncio

logger = logging.getLogger(__name__)

# Default for Docker deployments
DEFAULT_REDIS_URL = "redis://redis:6379/0"


def get_async_redis() -> redis.asyncio.Redis:
    """Get Redis client with config from environment variable or default."""
    url = os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)
    logger.debug(f"Connecting to Redis at {url}")
    return redis.asyncio.Redis.from_url(url, decode_responses=True)
