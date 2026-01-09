from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


class SafetyListsManager:
    """Manage persistent allow/deny lists with thread-safe updates."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.allow_patterns: list[str] = []
        self.deny_patterns: list[str] = []
        self.metadata: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._load()

    def __getstate__(self) -> dict[str, Any]:
        """Support for pickle/deepcopy - exclude lock."""
        return {
            "file_path": self.file_path,
            "allow_patterns": self.allow_patterns,
            "deny_patterns": self.deny_patterns,
            "metadata": self.metadata,
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore from pickle/deepcopy - recreate lock."""
        self.file_path = state["file_path"]
        self.allow_patterns = state["allow_patterns"]
        self.deny_patterns = state["deny_patterns"]
        self.metadata = state["metadata"]
        self._lock = threading.Lock()

    def _load(self) -> None:
        """Load lists from file."""
        if not self.file_path.exists():
            return

        try:
            with open(self.file_path, encoding="utf-8") as f:
                data = json.load(f)
                self.allow_patterns = data.get("allow_patterns", [])
                self.deny_patterns = data.get("deny_patterns", [])
                self.metadata = data.get("metadata", {})
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self) -> None:
        """Save lists to file."""
        data = {
            "allow_patterns": self.allow_patterns,
            "deny_patterns": self.deny_patterns,
            "metadata": {
                **self.metadata,
                "last_updated": datetime.now().isoformat(),
            },
        }

        temp_path = self.file_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        temp_path.replace(self.file_path)

    def add_allow_pattern(self, pattern: str) -> None:
        """Add pattern to allow-list and save."""
        with self._lock:
            if pattern not in self.allow_patterns:
                self.allow_patterns.append(pattern)
                self._save()

    def add_deny_pattern(self, pattern: str) -> None:
        """Add pattern to deny-list and save."""
        with self._lock:
            if pattern not in self.deny_patterns:
                self.deny_patterns.append(pattern)
                self._save()

    def get_allow_patterns(self) -> list[str]:
        """Get current allow patterns."""
        with self._lock:
            return self.allow_patterns.copy()

    def get_deny_patterns(self) -> list[str]:
        """Get current deny patterns."""
        with self._lock:
            return self.deny_patterns.copy()

    def remove_pattern(self, pattern: str) -> None:
        """Remove pattern from both lists."""
        with self._lock:
            if pattern in self.allow_patterns:
                self.allow_patterns.remove(pattern)
                self._save()
            if pattern in self.deny_patterns:
                self.deny_patterns.remove(pattern)
                self._save()
