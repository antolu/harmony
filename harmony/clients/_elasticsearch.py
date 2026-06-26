from __future__ import annotations

import logging
import typing

import pydantic
from elasticsearch import AsyncElasticsearch

from harmony.core._elasticsearch_config import ESConfig

logger = logging.getLogger(__name__)


class ElasticsearchService:
    def __init__(self, host: str, es_config: ESConfig | None = None) -> None:
        self._host = host
        self._es_config = es_config
        self.client = AsyncElasticsearch([self._host])

    async def close(self) -> None:
        await self.client.close()

    async def health_check(self) -> bool:
        try:
            return await self.client.ping()
        except Exception:
            return False

    async def get_document(
        self,
        doc_id: str,
        language: str | None = None,
        index: str | None = None,
    ) -> dict[str, pydantic.JsonValue]:
        if not self._es_config and not index:
            msg = "es_config must be provided to use language indices"
            raise ValueError(msg)

        if index:
            idx = index
        elif language and self._es_config:
            idx = self._es_config.get_index_name(language)
        elif self._es_config:
            idx = self._es_config.get_all_indices()[0]
        else:
            msg = "index or es_config must be provided"
            raise ValueError(msg)

        response = await self.client.get(index=idx, id=doc_id)
        return response["_source"]

    async def get_documents_by_ids(
        self,
        doc_ids: list[str],
        acl_terms: list[str],
    ) -> dict[str, dict[str, pydantic.JsonValue]]:
        """ACL-scoped batch lookup of documents by _id (the document URL).

        Returns a {doc_id: _source} map containing only documents the caller's
        roles are permitted to read. Unknown or unauthorized ids are omitted, so
        the caller falls back to whatever it has (a stored snapshot or hostname).
        """
        if not doc_ids or not acl_terms or not self._es_config:
            return {}

        response = await self.client.search(
            index=",".join(self._es_config.get_all_indices()),
            query={
                "bool": {
                    "filter": [
                        {"ids": {"values": doc_ids}},
                        {"terms": {"acl.allowed_roles": acl_terms}},
                        {"exists": {"field": "acl.policy_version"}},
                    ]
                }
            },
            size=len(doc_ids),
            source={"includes": ["url", "title", "content", "domain"]},
        )
        return {
            hit["_id"]: hit["_source"]
            for hit in response.get("hits", {}).get("hits", [])
        }

    async def index_exists(self, name: str) -> bool:
        return bool(await self.client.indices.exists(index=name))

    async def delete_index(self, name: str) -> None:
        await self.client.indices.delete(index=name)

    async def get_index_stats(self, name: str) -> dict[str, pydantic.JsonValue]:
        return typing.cast(
            dict[str, pydantic.JsonValue],
            dict(await self.client.indices.stats(index=name)),
        )

    async def list_indices(self, pattern: str) -> list[str]:
        try:
            result = await self.client.indices.get(index=pattern)
            return list(result.keys())
        except Exception as e:
            if "index_not_found_exception" in str(e):
                return []
            raise
