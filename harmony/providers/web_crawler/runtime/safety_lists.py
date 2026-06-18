from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from harmony.providers.web_crawler.runtime.writers import SafetyListsWriter


class SafetyListsManager:
    """Manage persistent allow/deny lists backed by a writer."""

    def __init__(self, writer: SafetyListsWriter) -> None:
        self._writer = writer
        self.allow_patterns: list[str] = []
        self.deny_patterns: list[str] = []
        self._load()

    def _load(self) -> None:
        self.allow_patterns, self.deny_patterns = self._writer.load()

    def add_allow_pattern(self, pattern: str) -> None:
        if pattern not in self.allow_patterns:
            self.allow_patterns.append(pattern)
            self._writer.add(pattern, "allow")

    def add_deny_pattern(self, pattern: str) -> None:
        if pattern not in self.deny_patterns:
            self.deny_patterns.append(pattern)
            self._writer.add(pattern, "deny")

    def get_allow_patterns(self) -> list[str]:
        return self.allow_patterns.copy()

    def get_deny_patterns(self) -> list[str]:
        return self.deny_patterns.copy()

    def remove_pattern(self, pattern: str) -> None:
        changed = False
        if pattern in self.allow_patterns:
            self.allow_patterns.remove(pattern)
            changed = True
        if pattern in self.deny_patterns:
            self.deny_patterns.remove(pattern)
            changed = True
        if changed:
            self._writer.remove(pattern)
