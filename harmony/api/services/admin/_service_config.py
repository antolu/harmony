from __future__ import annotations

import logging
import os
import typing

import httpx
import redis.asyncio as redis
from elasticsearch import AsyncElasticsearch

from harmony.db.connection import get_async_pool
from harmony.db.repositories import ServiceConfigRepo

logger = logging.getLogger(__name__)


class ServiceConfigStore:
    """Service configuration store with priority: ENV VAR > DATABASE > DEFAULT."""

    _repo: ServiceConfigRepo | None = None
    _initialized: bool = False

    # Default values for Docker deployments
    DEFAULTS: typing.ClassVar[dict[str, str]] = {
        "elasticsearch_url": "http://elasticsearch:9200",
        "redis_url": "redis://redis:6379/0",
        "es_index_base_name": "harmony",
        "es_languages": "en,fr",
        "es_state_index": "harmony-crawl-state",
        "ollama_host": "",
    }

    DESCRIPTIONS: typing.ClassVar[dict[str, str]] = {
        "elasticsearch_url": "Elasticsearch connection URL",
        "redis_url": "Redis connection URL",
        "es_index_base_name": "Base name for Elasticsearch indices",
        "es_languages": "Comma-separated list of language codes for indexing",
        "es_state_index": "Elasticsearch crawl state index name",
        "ollama_host": "Ollama server URL (leave empty to disable Ollama)",
    }

    # Environment variable mapping (static)
    _ENV_MAP: typing.ClassVar[dict[str, str]] = {
        "elasticsearch_url": "ES_HOST",
        "redis_url": "REDIS_URL",
        "es_index_base_name": "ES_INDEX_BASE_NAME",
        "es_languages": "ES_LANGUAGES",
        "es_state_index": "ES_STATE_INDEX",
        "ollama_host": "OLLAMA_HOST",
    }

    async def initialize(self, pool: object | None = None) -> None:
        """Initialize the service config store with an async connection pool."""
        if self._initialized:
            return

        resolved_pool = pool or await get_async_pool()
        self._repo = ServiceConfigRepo(resolved_pool)
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

    def is_from_env(self, key: str) -> bool:
        """Return True if the key is set via environment variable."""
        return bool(self._get_from_env(key))

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

    async def validate_ollama(self, url: str) -> tuple[bool, str]:
        """Test Ollama connectivity."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{url}/api/tags")
                resp.raise_for_status()
                models = resp.json().get("models", [])
                count = len(models)
                return (
                    True,
                    f"Connected ({count} model{'s' if count != 1 else ''} available)",
                )
        except Exception as e:
            logger.warning(f"Ollama validation failed for {url}: {e}")
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
