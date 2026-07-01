from __future__ import annotations

import time
import typing

import pytest

from harmony.services import (
    DocumentCache,
    RedisDocumentCache,
    make_document_cache,
)


class FakeRedis:
    """Minimal synchronous in-memory Redis stand-in supporting the subset
    RedisDocumentCache uses (set with ex, get, scan_iter, delete)."""

    def __init__(self) -> None:
        self.store: dict[str, tuple[str, float | None]] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        expiry = time.time() + ex if ex else None
        self.store[key] = (value, expiry)

    def _live(self, key: str) -> str | None:
        item = self.store.get(key)
        if item is None:
            return None
        value, expiry = item
        if expiry is not None and time.time() > expiry:
            del self.store[key]
            return None
        return value

    def get(self, key: str) -> str | None:
        return self._live(key)

    def scan_iter(self, match: str | None = None) -> typing.Iterator[str]:
        prefix = match.rstrip("*") if match else ""
        for key in list(self.store.keys()):
            if key.startswith(prefix) and self._live(key) is not None:
                yield key

    def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                removed += 1
        return removed


def test_set_then_get_round_trips() -> None:
    cache = RedisDocumentCache(redis_client=FakeRedis(), ttl=3600, max_size=1000)
    cache.set("https://example.com/a", "hello")
    assert cache.get("https://example.com/a") == "hello"


def test_get_missing_returns_none() -> None:
    cache = RedisDocumentCache(redis_client=FakeRedis(), ttl=3600, max_size=1000)
    assert cache.get("https://example.com/missing") is None


def test_entries_expire_via_ttl() -> None:
    cache = RedisDocumentCache(redis_client=FakeRedis(), ttl=1, max_size=1000)
    cache.set("https://example.com/a", "hello")
    time.sleep(1.1)
    assert cache.get("https://example.com/a") is None


def test_clear_only_removes_namespaced_keys() -> None:
    redis = FakeRedis()
    redis.set("unrelated:key", "keepme")
    cache = RedisDocumentCache(redis_client=redis, ttl=3600, max_size=1000)
    cache.set("https://example.com/a", "hello")
    cache.set("https://example.com/b", "world")
    cache.clear()
    assert cache.get("https://example.com/a") is None
    assert cache.get("https://example.com/b") is None
    assert redis.get("unrelated:key") == "keepme"


def test_size_counts_namespaced_keys() -> None:
    cache = RedisDocumentCache(redis_client=FakeRedis(), ttl=3600, max_size=1000)
    cache.set("https://example.com/a", "hello")
    cache.set("https://example.com/b", "world")
    assert cache.size() == 2


def test_stats_reports_size_and_ttl() -> None:
    cache = RedisDocumentCache(redis_client=FakeRedis(), ttl=42, max_size=7)
    cache.set("https://example.com/a", "hello")
    stats = cache.stats()
    assert stats.size == 1
    assert stats.ttl_seconds == 42
    assert stats.max_size == 7


def test_factory_returns_memory_cache() -> None:
    cache = make_document_cache("memory", redis=None, ttl=3600, max_size=1000)
    assert isinstance(cache, DocumentCache)


def test_factory_returns_redis_cache() -> None:
    cache = make_document_cache("redis", redis=FakeRedis(), ttl=3600, max_size=1000)
    assert isinstance(cache, RedisDocumentCache)


def test_factory_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="backend"):
        make_document_cache("memcached", redis=None, ttl=3600, max_size=1000)
