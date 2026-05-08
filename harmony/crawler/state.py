from __future__ import annotations

import typing
from datetime import UTC, datetime

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from harmony.crawler.logger import logger


class CrawlStateData(typing.TypedDict, total=False):
    url: str
    domain: str
    content_hash: str
    last_modified: str | None
    etag: str | None
    last_crawled_at: str | None
    last_seen_at: str | None
    status_code: int
    missing_count: int
    content_type: str
    file_path: str
    depth: int
    language: str


class CrawlStateManager:
    """Manages crawl state in Elasticsearch for change detection and deletion tracking."""

    def __init__(self, es_host: str, index_name: str = "harmony-crawl-state") -> None:
        self.es_host = es_host
        self.index_name = index_name
        self.client = Elasticsearch(es_host)
        self._ensure_index()

    def __getstate__(self) -> dict[str, typing.Any]:
        """Support for pickle/deepcopy - exclude ES client."""
        return {"es_host": self.es_host, "index_name": self.index_name}

    def __setstate__(self, state: dict[str, typing.Any]) -> None:
        """Restore from pickle/deepcopy - recreate ES client."""
        self.es_host = state["es_host"]
        self.index_name = state["index_name"]
        self.client = Elasticsearch(self.es_host)
        # Note: Don't call _ensure_index() here to avoid recreation on unpickle

    def _ensure_index(self) -> None:
        """Create the state index if it doesn't exist."""
        if self.client.indices.exists(index=self.index_name):
            return

        mappings = {
            "properties": {
                "url": {"type": "keyword"},
                "domain": {"type": "keyword"},
                "content_hash": {"type": "keyword"},
                "last_modified": {"type": "date"},
                "etag": {"type": "keyword"},
                "last_crawled_at": {"type": "date"},
                "last_seen_at": {"type": "date"},
                "status_code": {"type": "integer"},
                "missing_count": {"type": "integer"},
                "content_type": {"type": "keyword"},
                "file_path": {"type": "keyword"},
                "depth": {"type": "integer"},
                "language": {"type": "keyword"},
            }
        }

        self.client.indices.create(index=self.index_name, mappings=mappings)
        logger.info(f"Created crawl state index: {self.index_name}")

    def get_state(self, url: str) -> CrawlStateData | None:
        """Get crawl state for a URL."""
        try:
            response = self.client.get(index=self.index_name, id=url)
            return response["_source"]
        except Exception:
            return None

    def get_states_bulk(self, urls: list[str]) -> dict[str, CrawlStateData]:
        """Get crawl states for multiple URLs in bulk."""
        if not urls:
            return {}

        docs = [{"_index": self.index_name, "_id": url} for url in urls]
        response = self.client.mget(body={"docs": docs})

        states = {}
        for item in response["docs"]:
            if item["found"]:
                states[item["_id"]] = item["_source"]

        return states

    def update_state(self, url: str, state: CrawlStateData) -> None:
        """Update crawl state for a URL using upsert."""
        self.client.update(
            index=self.index_name,
            id=url,
            doc=state,
            doc_as_upsert=True,
        )

    def update_states_bulk(self, states: dict[str, CrawlStateData]) -> None:
        """Update crawl states for multiple URLs in bulk."""
        if not states:
            return

        actions = [
            {"_index": self.index_name, "_id": url, "_source": state}
            for url, state in states.items()
        ]

        _success, errors = bulk(self.client, actions, raise_on_error=False)
        if errors:
            logger.warning(f"Bulk update had {len(errors)} errors")

    def mark_seen(self, url: str) -> None:
        """Mark URL as seen (304 Not Modified or hash match)."""
        now = datetime.now(UTC).isoformat()
        self.client.update(
            index=self.index_name, id=url, doc={"last_seen_at": now}, doc_as_upsert=True
        )

    def increment_missing(self, url: str) -> None:
        """Increment missing count for a URL (404/Gone)."""
        now = datetime.now(UTC).isoformat()

        try:
            # Use scripted update to increment atomically without GET
            self.client.update(
                index=self.index_name,
                id=url,
                script={
                    "source": "ctx._source.missing_count = (ctx._source.missing_count ?: 0) + 1; ctx._source.last_seen_at = params.now",
                    "params": {"now": now},
                },
                upsert={"missing_count": 1, "last_seen_at": now},
            )
        except Exception as e:
            logger.error(f"Failed to increment missing count for {url}: {e}")

    def get_urls_to_delete(self, threshold: int = 3) -> list[str]:
        """Get URLs that have been missing for threshold or more crawls."""
        query = {"query": {"range": {"missing_count": {"gte": threshold}}}}

        try:
            response = self.client.search(
                index=self.index_name, body=query, size=10000, _source=False
            )
            return [hit["_id"] for hit in response["hits"]["hits"]]
        except Exception as e:
            logger.error(f"Failed to query URLs to delete: {e}")
            return []

    def get_stale_urls(self, max_age_days: int) -> list[str]:
        """Get URLs older than max_age_days for re-crawling."""
        query = {
            "query": {
                "range": {
                    "last_crawled_at": {"lte": f"now-{max_age_days}d"},
                }
            }
        }

        try:
            response = self.client.search(
                index=self.index_name, body=query, size=10000, _source=False
            )
            return [hit["_id"] for hit in response["hits"]["hits"]]
        except Exception as e:
            logger.error(f"Failed to query stale URLs: {e}")
            return []

    def delete_states(self, urls: list[str]) -> None:
        """Delete crawl states for multiple URLs."""
        if not urls:
            return

        actions = [
            {"_op_type": "delete", "_index": self.index_name, "_id": url}
            for url in urls
        ]

        success, errors = bulk(self.client, actions, raise_on_error=False)
        if errors:
            logger.warning(f"Bulk delete had {len(errors)} errors")
        else:
            logger.info(f"Deleted {success} state records")
