from __future__ import annotations

import dataclasses
import time


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
