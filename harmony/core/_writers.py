from __future__ import annotations

import json
import logging
import os
import threading
import typing
from datetime import datetime
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class SessionData(typing.TypedDict, total=False):
    subdomain: str  # present in to_dict() output but absent in DB-only load
    provider_type: str
    domain_pattern: str
    cookies: dict[str, str]
    headers: dict[str, str]
    storage_state_file: str | None
    created_at: str | None
    expires_at: str | None


class StatsPayload(typing.TypedDict, total=False):
    phase: str
    indexed: int
    total: int
    pages_crawled: int
    pages_pending: int
    requests_made: int
    pages_per_min: float
    current_url: str | None
    documents_indexed: int
    total_documents: int
    current_phase: str | None
    timestamp: str | None


class SafetyListsWriter(typing.Protocol):
    def load(self) -> tuple[list[str], list[str]]: ...
    def add(self, pattern: str, list_type: str) -> None: ...
    def remove(self, pattern: str) -> None: ...


class SessionWriter(typing.Protocol):
    def load(self) -> list[SessionData]: ...
    def upsert(self, session: SessionData) -> None: ...
    def invalidate(self, subdomain: str) -> None: ...


class StatsWriter(typing.Protocol):
    def publish(self, payload: StatsPayload) -> None: ...


# ---------------------------------------------------------------------------
# Backend implementations (HTTP to admin API)
# ---------------------------------------------------------------------------


class BackendSafetyListsWriter:
    def __init__(self, backend_url: str) -> None:
        self._base = backend_url.rstrip("/")

    def load(self) -> tuple[list[str], list[str]]:
        resp = httpx.get(f"{self._base}/api/internal/safety-lists", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return data.get("allow", []), data.get("deny", [])

    def add(self, pattern: str, list_type: str) -> None:
        try:
            httpx.post(
                f"{self._base}/api/internal/safety-lists",
                json={"pattern": pattern, "list_type": list_type},
                timeout=5,
            ).raise_for_status()
        except Exception as e:
            logger.warning(f"Failed to persist safety pattern: {e}")

    def remove(self, pattern: str) -> None:
        try:
            httpx.delete(
                f"{self._base}/api/internal/safety-lists",
                params={"pattern": pattern},
                timeout=5,
            ).raise_for_status()
        except Exception as e:
            logger.warning(f"Failed to remove safety pattern: {e}")


class BackendSessionWriter:
    def __init__(self, backend_url: str) -> None:
        self._base = backend_url.rstrip("/")

    def load(self) -> list[SessionData]:
        resp = httpx.get(f"{self._base}/api/internal/auth-sessions", timeout=5)
        resp.raise_for_status()
        return resp.json()

    def upsert(self, session: SessionData) -> None:
        try:
            httpx.post(
                f"{self._base}/api/internal/auth-sessions",
                json=session,
                timeout=5,
            ).raise_for_status()
        except Exception as e:
            logger.warning(
                f"Failed to persist auth session for {session.get('subdomain')}: {e}"
            )

    def invalidate(self, subdomain: str) -> None:
        try:
            httpx.delete(
                f"{self._base}/api/internal/auth-sessions/{subdomain}",
                timeout=5,
            ).raise_for_status()
        except Exception as e:
            logger.warning(f"Failed to invalidate auth session for {subdomain}: {e}")


class BackendStatsWriter:
    def __init__(self, backend_url: str, job_id: str) -> None:
        self._url = f"{backend_url.rstrip('/')}/api/internal/stats/{job_id}"

    def publish(self, payload: StatsPayload) -> None:
        try:
            httpx.post(self._url, json=payload, timeout=5).raise_for_status()
        except Exception as e:
            logger.debug(f"Failed to publish stats: {e}")


# ---------------------------------------------------------------------------
# File implementations (debug / standalone crawl)
# ---------------------------------------------------------------------------


class FileSafetyListsWriter:
    def __init__(self, state_dir: Path) -> None:
        self._path = state_dir / "safety-lists.json"
        self._lock = threading.RLock()

    def load(self) -> tuple[list[str], list[str]]:
        with self._lock:
            if not self._path.exists():
                return [], []
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                return data.get("allow_patterns", []), data.get("deny_patterns", [])
            except (json.JSONDecodeError, OSError):
                return [], []

    def _save(self, allow: list[str], deny: list[str]) -> None:
        with self._lock:
            data = {
                "allow_patterns": allow,
                "deny_patterns": deny,
                "metadata": {"last_updated": datetime.now().isoformat()},
            }
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(self._path)

    def add(self, pattern: str, list_type: str) -> None:
        with self._lock:
            allow, deny = self.load()
            if list_type == "allow" and pattern not in allow:
                allow.append(pattern)
                self._save(allow, deny)
            elif list_type == "deny" and pattern not in deny:
                deny.append(pattern)
                self._save(allow, deny)

    def remove(self, pattern: str) -> None:
        with self._lock:
            allow, deny = self.load()
            changed = False
            if pattern in allow:
                allow.remove(pattern)
                changed = True
            if pattern in deny:
                deny.remove(pattern)
                changed = True
            if changed:
                self._save(allow, deny)


class FileSessionWriter:
    def __init__(self, state_dir: Path) -> None:
        self._path = state_dir / "sessions.json"

    def load(self) -> list[SessionData]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return list(data.values())
        except (json.JSONDecodeError, OSError):
            return []

    def _load_raw(self) -> dict[str, typing.Any]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def upsert(self, session: SessionData) -> None:
        data = self._load_raw()
        subdomain = session.get("subdomain", "")
        data[subdomain] = session
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def invalidate(self, subdomain: str) -> None:
        data = self._load_raw()
        if subdomain in data:
            del data[subdomain]
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class FileStatsWriter:
    def __init__(self, state_dir: Path, job_id: str | None = None) -> None:
        self._path = state_dir / "stats.json"

    def publish(self, payload: StatsPayload) -> None:
        try:
            self._path.write_text(json.dumps(payload), encoding="utf-8")
        except OSError as e:
            logger.debug(f"Failed to write stats file: {e}")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_writers(
    output_dir: Path,
    job_id: str | None = None,
) -> tuple[SafetyListsWriter, SessionWriter, StatsWriter]:
    state_dir = output_dir / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)

    backend_url = os.environ.get("HARMONY_BACKEND_URL")

    if backend_url:
        safety_writer: SafetyListsWriter = BackendSafetyListsWriter(backend_url)
        session_writer: SessionWriter = BackendSessionWriter(backend_url)
        stats_writer: StatsWriter = (
            BackendStatsWriter(backend_url, job_id)
            if job_id
            else FileStatsWriter(state_dir)
        )
    else:
        safety_writer = FileSafetyListsWriter(state_dir)
        session_writer = FileSessionWriter(state_dir)
        stats_writer = FileStatsWriter(state_dir, job_id)

    return safety_writer, session_writer, stats_writer
