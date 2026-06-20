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
        "auth_mode": "optional",
        "harmony_public_url": "",
        "oidc_issuer_url": "",
        "oidc_internal_url": "",
        "oidc_client_id": "",
        "oidc_client_secret": "",
        "oidc_scopes": "openid profile email",
        "oidc_role_claim_key": "",
        "oidc_role_mapping": "{}",
        "service_api_key": "",
        "harmony_bootstrap_admin_sub": "",
        "jwt_private_key_pem": "",
        "jwt_public_key_pem": "",
        "brave_api_key": "",
        "google_api_key": "",
        "harmony_secret_key": "",
        "external_search_enabled": "false",
        "external_search_brave_enabled": "false",
        "external_search_google_enabled": "false",
        "external_search_allowed_roles": "admin",
        "external_search_brave_limit": "5",
        "external_search_google_limit": "5",
        "google_search_cx": "",
        "data_residency_mode": "false",
        "feedback_enabled": "true",
        "pipeline_keyword_candidates_n": "50",
        "pipeline_vector_top_k": "20",
        "pipeline_search_top_k": "5",
        "pipeline_vector_search_enabled": "true",
        "pipeline_reranker_enabled": "false",
        "pipeline_agentic_max_refinement_rounds": "3",
        "pipeline_agentic_max_query_variants": "4",
        "pipeline_agentic_search_top_k": "10",
        "pipeline_agentic_max_sources_returned": "10",
        "audit_retention_days": "90",
        "conversation_ttl_days": "0",
        "index_threshold_count": "0",
    }

    DESCRIPTIONS: typing.ClassVar[dict[str, str]] = {
        "elasticsearch_url": "Elasticsearch connection URL",
        "redis_url": "Redis connection URL",
        "es_index_base_name": "Base name for Elasticsearch indices",
        "es_languages": "Comma-separated list of language codes for indexing",
        "es_state_index": "Elasticsearch crawl state index name",
        "ollama_host": "Ollama server URL (leave empty to disable Ollama)",
        "auth_mode": "Authentication mode: optional, required, or oidc",
        "oidc_issuer_url": "OIDC provider issuer URL",
        "oidc_client_id": "OIDC client ID",
        "oidc_scopes": "Space-separated OIDC scopes to request",
        "oidc_role_claim_key": "JWT claim key for role mapping",
        "oidc_role_mapping": "JSON mapping of OIDC role values to harmony roles",
        "harmony_bootstrap_admin_sub": "OIDC sub of the initial bootstrap admin user",
        "jwt_public_key_pem": "PEM-encoded public key for JWT verification",
        "feedback_enabled": "Whether thumbs up/down feedback is shown on chat messages",
        "index_threshold_count": "Fire index_threshold webhook after this many documents indexed (0 = disabled)",
    }

    # Secret keys — omitted from DESCRIPTIONS so they are not exposed via API
    _SECRET_KEYS: typing.ClassVar[frozenset[str]] = frozenset({
        "oidc_client_secret",
        "service_api_key",
        "jwt_private_key_pem",
        "brave_api_key",
        "google_api_key",
        "harmony_secret_key",
    })

    # Environment variable mapping (static)
    _ENV_MAP: typing.ClassVar[dict[str, str]] = {
        "elasticsearch_url": "ES_HOST",
        "redis_url": "REDIS_URL",
        "es_index_base_name": "ES_INDEX_BASE_NAME",
        "es_languages": "ES_LANGUAGES",
        "es_state_index": "ES_STATE_INDEX",
        "ollama_host": "OLLAMA_HOST",
        "auth_mode": "AUTH_MODE",
        "harmony_public_url": "HARMONY_PUBLIC_URL",
        "oidc_issuer_url": "OIDC_ISSUER_URL",
        "oidc_internal_url": "OIDC_INTERNAL_URL",
        "oidc_client_id": "OIDC_CLIENT_ID",
        "oidc_client_secret": "OIDC_CLIENT_SECRET",
        "oidc_scopes": "OIDC_SCOPES",
        "oidc_role_claim_key": "OIDC_ROLE_CLAIM_KEY",
        "oidc_role_mapping": "OIDC_ROLE_MAPPING",
        "service_api_key": "SERVICE_API_KEY",
        "harmony_bootstrap_admin_sub": "HARMONY_BOOTSTRAP_ADMIN_SUB",
        "jwt_private_key_pem": "JWT_PRIVATE_KEY_PEM",
        "jwt_public_key_pem": "JWT_PUBLIC_KEY_PEM",
        "audit_retention_days": "AUDIT_RETENTION_DAYS",
        "conversation_ttl_days": "CONVERSATION_TTL_DAYS",
    }

    async def initialize(self, pool: object | None = None) -> None:
        """Initialize the service config store with an async connection pool."""
        if self._initialized:
            return

        resolved_pool = pool or await get_async_pool()
        self._repo = ServiceConfigRepo(resolved_pool)  # type: ignore[arg-type]
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
            display_value = "[REDACTED]" if key in self._SECRET_KEYS else env_value
            logger.debug(f"Config '{key}' from environment variable: {display_value}")
            return env_value

        # Priority 2: Database
        if self._repo:
            try:
                config = await self._repo.get(key)
                if config and config.get("is_configured"):
                    value = config["value"]
                    display_value = "[REDACTED]" if key in self._SECRET_KEYS else value
                    logger.debug(f"Config '{key}' from database: {display_value}")
                    return value
            except Exception as e:
                logger.warning(f"Failed to get config '{key}' from database: {e}")

        # Priority 3: Default
        default = self.DEFAULTS.get(key, "")
        display_value = "[REDACTED]" if key in self._SECRET_KEYS else default
        logger.debug(f"Config '{key}' using default: {display_value}")
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
        display = "[REDACTED]" if key in self._SECRET_KEYS else value
        logger.info(f"Saved config '{key}': {display} (validated: {validated})")

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

    async def get_external_search_defaults_for_roles(self) -> dict[str, bool]:
        result: dict[str, bool] = {}
        prefix = "external_search_default_"
        if self._repo:
            try:
                all_configs = await self._repo.get_all()
                for config in all_configs:
                    key = config["key"]
                    if key.startswith(prefix) and config.get("is_configured"):
                        role = key[len(prefix) :]
                        result[role] = config["value"] == "on"
            except Exception as e:
                logger.warning(f"Failed to list external search default role keys: {e}")
        return result

    async def set_external_search_default_for_role(
        self, role: str, *, default_on: bool
    ) -> None:
        await self.set(f"external_search_default_{role}", "on" if default_on else "off")

    async def get_status(self) -> dict[str, str]:
        """Get current status of all configurations."""
        status = {}
        for key in self.DEFAULTS:
            value = await self.get(key)
            status[key] = "[REDACTED]" if key in self._SECRET_KEYS and value else value
        return status
