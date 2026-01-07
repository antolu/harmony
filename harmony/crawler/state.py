from __future__ import annotations

import typing
from datetime import UTC, datetime

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from harmony.crawler.logger import logger


class CrawlStateManager:
    """Manages crawl state in Elasticsearch for change detection and deletion tracking."""

    def __init__(self, es_host: str, index_name: str = "harmony-crawl-state") -> None:
        self.client = Elasticsearch(es_host)
        self.index_name = index_name
        self._ensure_index()

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
            }
        }

        self.client.indices.create(index=self.index_name, mappings=mappings)
        logger.info(f"Created crawl state index: {self.index_name}")

    def get_state(self, url: str) -> dict[str, typing.Any] | None:
        """Get crawl state for a URL."""
        try:
            response = self.client.get(index=self.index_name, id=url)
            return response["_source"]
        except Exception:
            return None

    def get_states_bulk(self, urls: list[str]) -> dict[str, dict[str, typing.Any]]:
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

    def update_state(self, url: str, state: dict[str, typing.Any]) -> None:
        """Update crawl state for a URL."""
        self.client.index(index=self.index_name, id=url, document=state)

    def update_states_bulk(self, states: dict[str, dict[str, typing.Any]]) -> None:
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
            state = self.get_state(url)
            missing_count = (state.get("missing_count", 0) if state else 0) + 1

            self.client.update(
                index=self.index_name,
                id=url,
                doc={"missing_count": missing_count, "last_seen_at": now},
                doc_as_upsert=True,
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
