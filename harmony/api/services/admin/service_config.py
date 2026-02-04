from __future__ import annotations

import logging
import os
import typing

import redis.asyncio as redis
from elasticsearch import AsyncElasticsearch

from harmony.db.connection import get_async_pool
from harmony.db.repositories import ServiceConfigRepo

logger = logging.getLogger(__name__)


class ServiceConfigStore:
    """Service configuration store with priority: ENV VAR > DATABASE > DEFAULT."""

    _instance: typing.ClassVar[ServiceConfigStore | None] = None
    _repo: ServiceConfigRepo | None = None
    _initialized: bool = False

    # Default values for Docker deployments
    DEFAULTS: typing.ClassVar[dict[str, str]] = {
        "elasticsearch_url": "http://elasticsearch:9200",
        "redis_url": "redis://redis:6379/0",
    }

    DESCRIPTIONS: typing.ClassVar[dict[str, str]] = {
        "elasticsearch_url": "Elasticsearch connection URL",
        "redis_url": "Redis connection URL",
    }

    # Environment variable mapping (static)
    _ENV_MAP: typing.ClassVar[dict[str, str]] = {
        "elasticsearch_url": "ES_HOST",
        "redis_url": "REDIS_URL",
    }

    def __new__(cls) -> typing.Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance  # type: ignore[return-value]

    async def initialize(self) -> None:
        """Initialize the service config store."""
        if self._initialized:
            return

        pool = get_async_pool()
        self._repo = ServiceConfigRepo(pool)
        self._initialized = True
        logger.info("ServiceConfigStore initialized")

    def _get_from_env(self, key: str) -> str | None:
        """Get value from environment variable."""
        env_var = self._ENV_MAP.get(key)
        if env_var:
            return os.environ.get(env_var)
        return None

    async def get(self, key: str) -> str:
        """Get configuration value with priority: ENV VAR > DATABASE > DEFAULT.

        Returns the config value and logs the source for transparency.
        """
        # Priority 1: Environment variable
        env_value = self._get_from_env(key)
        if env_value:
            logger.debug(f"Config '{key}' from environment variable: {env_value}")
            return env_value

        # Priority 2: Database
        if self._repo:
            try:
                config = await self._repo.get(key)
                if config and config.get("is_configured"):
                    value = config["value"]
                    logger.debug(f"Config '{key}' from database: {value}")
                    return value
            except Exception as e:
                logger.warning(f"Failed to get config '{key}' from database: {e}")

        # Priority 3: Default
        default = self.DEFAULTS.get(key, "")
        logger.debug(f"Config '{key}' using default: {default}")
        return default

    def get_source(self, key: str) -> str:
        """Get the source of a configuration value (for logging)."""
        if self._get_from_env(key):
            return "environment variable"
        # Note: This simplified version always returns the sync check
        # In real usage, the actual source is logged in get()
        return "database or default"

    async def set(self, key: str, value: str, *, validated: bool = True) -> None:
        """Save configuration to database."""
        if not self._repo:
            msg = "ServiceConfigStore not initialized"
            raise RuntimeError(msg)

        description = self.DESCRIPTIONS.get(key)
        await self._repo.upsert(key, value, description, validated=validated)
        logger.info(f"Saved config '{key}': {value} (validated: {validated})")

    async def is_configured(self) -> bool:
        """Check if initial setup is complete."""
        if not self._repo:
            return False
        return await self._repo.is_configured()

    async def validate_elasticsearch(self, url: str) -> tuple[bool, str]:
        """Test Elasticsearch connection."""
        try:
            async with AsyncElasticsearch([url]) as client:
                health = await client.cluster.health()
                if health.get("status") in {"green", "yellow", "red"}:
                    status_val = str(health.get("status"))
                    return (
                        True,
                        f"Connected successfully (cluster status: {status_val})",
                    )
                return False, "Unexpected health response"
        except Exception as e:
            logger.warning(f"Elasticsearch validation failed for {url}: {e}")
            return False, f"Connection failed: {e!s}"

    async def validate_redis(self, url: str) -> tuple[bool, str]:
        """Test Redis connection."""
        try:
            client = redis.from_url(url)
            await client.ping()
            await client.aclose()
        except Exception as e:
            logger.warning(f"Redis validation failed for {url}: {e}")
            return False, f"Connection failed: {e!s}"
        else:
            return True, "Connected successfully"

    async def get_status(self) -> dict[str, str]:
        """Get current status of all configurations."""
        status = {}
        for key in self.DEFAULTS:
            status[key] = await self.get(key)
        return status


# Singleton instance
service_config_store = ServiceConfigStore()
