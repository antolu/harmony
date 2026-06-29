from __future__ import annotations

import dataclasses
import hashlib
import time
import typing

if typing.TYPE_CHECKING:
    import redis

_REDIS_KEY_PREFIX = "doccache:"


@typing.runtime_checkable
class DocumentCacheProtocol(typing.Protocol):
    """Shared interface for the in-memory and Redis document caches."""

    def get(self, url: str) -> str | None: ...
    def set(self, url: str, content: str) -> None: ...
    def clear(self) -> None: ...
    def size(self) -> int: ...
    def stats(self) -> CacheStats: ...


@dataclasses.dataclass
class CacheEntry:
    """Cache entry with TTL."""

    content: str
    timestamp: float
    ttl: float

    def is_expired(self) -> bool:
        """Check if entry is expired."""
        return time.time() - self.timestamp > self.ttl


@dataclasses.dataclass
class CacheStats:
    size: int
    max_size: int
    ttl_seconds: float
    expired_entries: int


class DocumentCache:
    """In-memory TTL cache for fetched documents."""

    def __init__(self, ttl: int = 3600, max_size: int = 1000) -> None:
        self.cache: dict[str, CacheEntry] = {}
        self.ttl = float(ttl)
        self.max_size = max_size

    def get(self, url: str) -> str | None:
        """
        Get cached document if not expired.

        Args:
            url: Document URL

        Returns:
            Cached content or None if not found/expired
        """
        entry = self.cache.get(url)
        if not entry:
            return None

        if entry.is_expired():
            del self.cache[url]
            return None

        return entry.content

    def set(self, url: str, content: str) -> None:
        """
        Cache document content.

        Args:
            url: Document URL
            content: Document content
        """
        # Cleanup if cache is full
        if len(self.cache) >= self.max_size:
            self._cleanup_expired()

            # If still full, remove oldest entries
            if len(self.cache) >= self.max_size:
                self._remove_oldest(count=self.max_size // 10)

        self.cache[url] = CacheEntry(
            content=content, timestamp=time.time(), ttl=self.ttl
        )

    def _cleanup_expired(self) -> None:
        """Remove all expired entries."""
        expired_keys = [url for url, entry in self.cache.items() if entry.is_expired()]
        for key in expired_keys:
            del self.cache[key]

    def _remove_oldest(self, count: int) -> None:
        """Remove oldest N entries."""
        if not self.cache:
            return

        # Sort by timestamp and remove oldest
        sorted_entries = sorted(self.cache.items(), key=lambda x: x[1].timestamp)
        for url, _ in sorted_entries[:count]:
            del self.cache[url]

    def clear(self) -> None:
        """Clear entire cache."""
        self.cache.clear()

    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)

    def stats(self) -> CacheStats:
        """Get cache statistics."""
        expired_count = sum(1 for entry in self.cache.values() if entry.is_expired())
        return CacheStats(
            size=len(self.cache),
            max_size=self.max_size,
            ttl_seconds=self.ttl,
            expired_entries=expired_count,
        )


class RedisDocumentCache:
    """Redis-backed document cache sharing one interface with DocumentCache.

    Keeps get/set synchronous so the existing tool call sites (which call
    cache.get/cache.set without awaiting) are untouched — backed by a
    synchronous redis client. Keys are namespaced under a fixed prefix and
    hashed so arbitrary URLs are safe Redis keys; expiry is delegated to Redis
    TTL (no manual sweep).
    """

    def __init__(
        self, redis_client: redis.Redis, ttl: int = 3600, max_size: int = 1000
    ) -> None:
        self._redis = redis_client
        self.ttl = float(ttl)
        # Advisory only for Redis (maxmemory policy handles eviction); kept for
        # interface parity with DocumentCache.
        self.max_size = max_size

    @staticmethod
    def _key(url: str) -> str:
        return f"{_REDIS_KEY_PREFIX}{hashlib.sha256(url.encode()).hexdigest()}"

    def get(self, url: str) -> str | None:
        return self._redis.get(self._key(url))

    def set(self, url: str, content: str) -> None:
        self._redis.set(self._key(url), content, ex=int(self.ttl))

    def clear(self) -> None:
        keys = list(self._redis.scan_iter(match=f"{_REDIS_KEY_PREFIX}*"))
        if keys:
            self._redis.delete(*keys)

    def size(self) -> int:
        # Approximation via SCAN over the namespace prefix.
        return sum(1 for _ in self._redis.scan_iter(match=f"{_REDIS_KEY_PREFIX}*"))

    def stats(self) -> CacheStats:
        return CacheStats(
            size=self.size(),
            max_size=self.max_size,
            ttl_seconds=self.ttl,
            expired_entries=0,
        )


def make_document_cache(
    backend: str, *, redis: redis.Redis | None, ttl: int, max_size: int
) -> DocumentCacheProtocol:
    """Build a document cache for the selected backend.

    "memory" returns the in-process DocumentCache; "redis" returns a
    RedisDocumentCache backed by the provided synchronous redis client.
    """
    if backend == "memory":
        return DocumentCache(ttl=ttl, max_size=max_size)
    if backend == "redis":
        if redis is None:
            msg = "redis backend requires a redis client"
            raise ValueError(msg)
        return RedisDocumentCache(redis_client=redis, ttl=ttl, max_size=max_size)
    msg = f"Unknown document cache backend: {backend}"
    raise ValueError(msg)
