from __future__ import annotations

import dataclasses
import re
import typing

import httpx
import structlog
from kv_search import SearchHit

from harmony.api.authz import AuthorizationContext
from harmony.api.observability._secret_service import SecretValueService
from harmony.api.services.admin._service_config import ServiceConfigStore

logger = structlog.get_logger(__name__)

_ROLE_NAME_PATTERN = re.compile(r"^[a-z_]+$")


@dataclasses.dataclass(frozen=True)
class ExternalSearchContext:
    request_toggle: bool = False


@typing.runtime_checkable
class ExternalProvider(typing.Protocol):
    async def search(self, query: str, limit: int) -> list[SearchHit]: ...


class BraveProvider:
    def __init__(self, api_key: str, timeout: float = 5.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    async def search(self, query: str, limit: int) -> list[SearchHit]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": limit},
                    headers={
                        "X-Subscription-Token": self._api_key,
                        "Accept": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                items = data.get("web", {}).get("results", [])
                return [
                    SearchHit(
                        path=item.get("url", ""),
                        score=0.0,
                        metadata={
                            "title": item.get("title", ""),
                            "content": item.get("description", ""),
                            "source_type": "external",
                            "provider": "brave",
                        },
                    )
                    for item in items[:limit]
                ]
        except Exception as exc:
            logger.warning("brave_provider_error", error=str(exc))
            return []


class GoogleProvider:
    def __init__(self, api_key: str, cx: str, timeout: float = 5.0) -> None:
        self._api_key = api_key
        self._cx = cx
        self._timeout = timeout

    async def search(self, query: str, limit: int) -> list[SearchHit]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params={
                        "key": self._api_key,
                        "cx": self._cx,
                        "q": query,
                        "num": min(limit, 10),
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                items = data.get("items", [])
                return [
                    SearchHit(
                        path=item.get("link", ""),
                        score=0.0,
                        metadata={
                            "title": item.get("title", ""),
                            "content": item.get("snippet", ""),
                            "source_type": "external",
                            "provider": "google",
                        },
                    )
                    for item in items[:limit]
                ]
        except Exception as exc:
            logger.warning("google_provider_error", error=str(exc))
            return []


class ExternalSearchService:
    def __init__(
        self,
        service_config: ServiceConfigStore,
        secret_service: SecretValueService,
    ) -> None:
        self._config = service_config
        self._secret = secret_service

    async def _has_usable_key(self, config_key: str) -> bool:
        enc = await self._config.get(config_key)
        if not enc:
            return False
        try:
            return bool(self._secret.decrypt(enc))
        except Exception:
            return False

    async def is_allowed(
        self,
        authz_context: AuthorizationContext | None,
        *,
        request_toggle: bool,
    ) -> bool:
        data_residency = await self._config.get("data_residency_mode")
        if data_residency == "true":
            logger.info("external_search_skipped_data_residency")
            return False

        if await self._config.get("external_search_enabled") != "true":
            return False

        if not request_toggle:
            return False

        if authz_context is not None:
            allowed_roles_raw = await self._config.get("external_search_allowed_roles")
            allowed_roles = {
                r.strip() for r in allowed_roles_raw.split(",") if r.strip()
            }
            if not any(role in allowed_roles for role in authz_context.harmony_roles):
                return False

        has_brave = await self._has_usable_key("brave_api_key")
        has_google = await self._has_usable_key("google_api_key")
        return has_brave or has_google

    async def _fetch_brave(self, query: str, limit: int) -> list[SearchHit]:
        if await self._config.get("external_search_brave_enabled") != "true":
            return []
        enc = await self._config.get("brave_api_key")
        if not enc:
            return []
        try:
            key = self._secret.decrypt(enc)
            if not key:
                return []
            return await BraveProvider(api_key=key).search(query, limit)
        except Exception as exc:
            logger.warning("brave_key_decrypt_error", error=str(exc))
            return []

    async def _fetch_google(self, query: str, limit: int) -> list[SearchHit]:
        if await self._config.get("external_search_google_enabled") != "true":
            return []
        enc = await self._config.get("google_api_key")
        cx = await self._config.get("google_search_cx")
        if not enc or not cx:
            return []
        try:
            key = self._secret.decrypt(enc)
            if not key:
                return []
            return await GoogleProvider(api_key=key, cx=cx).search(query, limit)
        except Exception as exc:
            logger.warning("google_key_decrypt_error", error=str(exc))
            return []

    async def _resolve_limit(self, limit: int | None, config_key: str) -> int:
        if limit is not None:
            return limit
        try:
            return int(await self._config.get(config_key))
        except (ValueError, TypeError):
            return 5

    async def fetch_external_results(
        self,
        query: str,
        context: AuthorizationContext | None,
        *,
        request_toggle: bool,
        limit: int | None = None,
    ) -> list[SearchHit]:
        if not await self.is_allowed(context, request_toggle=request_toggle):
            return []

        if context is not None:
            structlog.contextvars.bind_contextvars(trace_id=context.trace_id)

        brave_limit = await self._resolve_limit(limit, "external_search_brave_limit")
        google_limit = await self._resolve_limit(limit, "external_search_google_limit")

        results: list[SearchHit] = []
        results.extend(await self._fetch_brave(query, brave_limit))
        results.extend(await self._fetch_google(query, google_limit))
        return results

    async def get_default_toggle_for_roles(self, harmony_roles: list[str]) -> bool:
        for role in harmony_roles:
            val = await self._config.get(f"external_search_default_{role}")
            if val == "on":
                return True
        return False
