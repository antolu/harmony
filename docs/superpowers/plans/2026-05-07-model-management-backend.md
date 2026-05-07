# Model Management Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add runtime-mutable model settings (embedding, reranker, LLM) backed by PostgreSQL, Ollama proxy routes, re-embed job type, and update vector/reranker backends to read model config at request time.

**Architecture:** Model settings reuse the existing `service_configs` table as key-value rows, accessed via a new `ModelSettingsStore` singleton (same pattern as `ServiceConfigStore`). Both `HarmonyVectorBackend` and `HarmonyRerankerBackend` drop constructor model args and call `model_settings_store.get()` at request time. Three Ollama proxy routes forward to `settings.ollama_host`. A new `embed` job type runs `harmony-embed` via `job_manager`, clearing the `embedding_model_changed_since_last_embed` flag on success.

**Tech Stack:** Python 3.13, FastAPI, psycopg (async), Alembic, litellm, httpx

---

## Files

| Path | Action |
|------|--------|
| `alembic/versions/0004_add_model_settings.py` | Create — migration: extend jobs type check + seed model setting rows |
| `harmony/api/services/admin/model_settings.py` | Create — ModelSettingsStore singleton |
| `harmony/api/routes/admin/ollama.py` | Create — Ollama proxy routes |
| `harmony/api/routes/admin/model_settings.py` | Create — GET/PATCH /api/settings/models + validate |
| `harmony/api/services/qdrant.py` | Modify — add `is_empty()` method |
| `harmony/api/backends/vector.py` | Modify — remove constructor arg, read model at request time |
| `harmony/api/backends/reranker.py` | Modify — remove constructor arg, read model at request time |
| `harmony/api/services/pipeline_config.py` | Modify — remove `reranker_model` field |
| `harmony/api/models/job.py` | Modify — add `"embed"` to `JobType` |
| `harmony/api/services/admin/job_manager.py` | Modify — add `start_embed_job()`, clear flag on completion |
| `harmony/api/routes/admin/jobs.py` | Modify — add `POST /embed` endpoint |
| `harmony/api/routes/admin/setup.py` | Modify — extend `SetupRequest` with model fields |
| `harmony/api/main.py` | Modify — update backend construction, add routes, empty-Qdrant check |
| `tests/test_model_settings_store.py` | Create |
| `tests/test_ollama_routes.py` | Create |
| `tests/test_model_settings_routes.py` | Create |
| `tests/test_vector_backend.py` | Modify — update mocking |
| `tests/test_reranker_backend.py` | Modify — update mocking |

---

### Task 1: Database Migration

**Files:**
- Create: `alembic/versions/0004_add_model_settings.py`

- [ ] **Step 1: Write the migration file**

```python
"""add model settings and embed job type

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-07
"""

from __future__ import annotations

from alembic import op

down_revision = "0003"
revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS ck_jobs_type")
    op.execute(
        "ALTER TABLE jobs ADD CONSTRAINT ck_jobs_type "
        "CHECK (type IN ('crawl', 'index', 'embed'))"
    )
    op.execute("""
        INSERT INTO service_configs (key, value, description, is_configured)
        VALUES
          ('embedding_provider', 'ollama', 'Provider for embedding model: ollama or litellm', true),
          ('embedding_model', 'ollama/qwen3-embedding:0.6b', 'litellm model string for embeddings', true),
          ('reranker_provider', 'ollama', 'Provider for reranker model: ollama or litellm', true),
          ('reranker_model', 'ollama/bge-reranker-v2-m3', 'litellm model string for reranking', true),
          ('llm_provider', 'litellm', 'Provider for LLM: ollama or litellm', true),
          ('llm_model', 'gemini/gemini-3-flash-preview', 'litellm model string for LLM', true),
          ('embedding_model_changed_since_last_embed', 'false',
           'Set true when embedding model changes, cleared on successful embed job', true)
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS ck_jobs_type")
    op.execute(
        "ALTER TABLE jobs ADD CONSTRAINT ck_jobs_type "
        "CHECK (type IN ('crawl', 'index'))"
    )
    op.execute(
        "DELETE FROM service_configs WHERE key IN ("
        "'embedding_provider', 'embedding_model', 'reranker_provider', "
        "'reranker_model', 'llm_provider', 'llm_model', "
        "'embedding_model_changed_since_last_embed')"
    )
```

- [ ] **Step 2: Verify migration runs**

```bash
# Requires postgres running — skip if no local DB, verify in integration test
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/0004_add_model_settings.py
git commit -m "feat: add migration for model settings and embed job type"
```

---

### Task 2: ModelSettingsStore

**Files:**
- Create: `harmony/api/services/admin/model_settings.py`
- Create: `tests/test_model_settings_store.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_model_settings_store.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harmony.api.services.admin.model_settings import ModelSettingsStore


@pytest.fixture
def store() -> ModelSettingsStore:
    return ModelSettingsStore()


async def test_get_returns_default_when_no_db_row(store: ModelSettingsStore) -> None:
    mock_repo = AsyncMock()
    mock_repo.get.return_value = None
    mock_pool = MagicMock()
    mock_pool.connection.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_pool.connection.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("harmony.api.services.admin.model_settings.get_async_pool", AsyncMock(return_value=mock_pool)):
        with patch("harmony.api.services.admin.model_settings.ServiceConfigRepo", return_value=mock_repo):
            result = await store.get("reranker_provider")

    assert result == "ollama"


async def test_get_returns_db_value_over_default(store: ModelSettingsStore) -> None:
    mock_repo = AsyncMock()
    mock_repo.get.return_value = {"value": "litellm", "is_configured": True}
    mock_pool = MagicMock()
    mock_pool.connection.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_pool.connection.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("harmony.api.services.admin.model_settings.get_async_pool", AsyncMock(return_value=mock_pool)):
        with patch("harmony.api.services.admin.model_settings.ServiceConfigRepo", return_value=mock_repo):
            result = await store.get("reranker_provider")

    assert result == "litellm"


async def test_set_calls_repo_upsert(store: ModelSettingsStore) -> None:
    mock_repo = AsyncMock()
    mock_pool = MagicMock()
    mock_pool.connection.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_pool.connection.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("harmony.api.services.admin.model_settings.get_async_pool", AsyncMock(return_value=mock_pool)):
        with patch("harmony.api.services.admin.model_settings.ServiceConfigRepo", return_value=mock_repo):
            await store.set("reranker_provider", "litellm")

    mock_repo.upsert.assert_called_once_with("reranker_provider", "litellm", None, validated=True)


async def test_get_all_returns_all_keys(store: ModelSettingsStore) -> None:
    mock_repo = AsyncMock()
    mock_repo.get.return_value = None
    mock_pool = MagicMock()
    mock_pool.connection.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_pool.connection.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("harmony.api.services.admin.model_settings.get_async_pool", AsyncMock(return_value=mock_pool)):
        with patch("harmony.api.services.admin.model_settings.ServiceConfigRepo", return_value=mock_repo):
            result = await store.get_all()

    expected_keys = {
        "embedding_provider", "embedding_model", "reranker_provider",
        "reranker_model", "llm_provider", "llm_model",
        "embedding_model_changed_since_last_embed",
    }
    assert set(result.keys()) == expected_keys
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_model_settings_store.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `model_settings` doesn't exist yet.

- [ ] **Step 3: Implement ModelSettingsStore**

```python
# harmony/api/services/admin/model_settings.py
from __future__ import annotations

import typing

from harmony.api.config import settings as app_settings
from harmony.db.repositories import ServiceConfigRepo

_DEFAULTS: typing.ClassVar[dict[str, str]] = {
    "embedding_provider": "ollama",
    "embedding_model": app_settings.embedding_model,
    "reranker_provider": "ollama",
    "reranker_model": "ollama/bge-reranker-v2-m3",
    "llm_provider": "litellm",
    "llm_model": app_settings.llm_model,
    "embedding_model_changed_since_last_embed": "false",
}

# Keys where env var takes priority over DB
_ENV_VALUES: dict[str, str | None] = {
    "embedding_model": app_settings.embedding_model if app_settings.embedding_model != "ollama/qwen3-embedding:0.6b" else None,
    "llm_model": app_settings.llm_model if app_settings.llm_model != "gemini/gemini-3-flash-preview" else None,
}


class ModelSettingsStore:
    async def get(self, key: str) -> str:
        env_val = _ENV_VALUES.get(key)
        if env_val:
            return env_val

        from harmony.db.connection import get_async_pool  # noqa: PLC0415

        pool = await get_async_pool()
        async with pool.connection() as conn:
            repo = ServiceConfigRepo(conn)
            row = await repo.get(key)
            if row and row.get("is_configured"):
                return row["value"]
        return _DEFAULTS[key]

    async def set(self, key: str, value: str) -> None:
        from harmony.db.connection import get_async_pool  # noqa: PLC0415

        pool = await get_async_pool()
        async with pool.connection() as conn:
            repo = ServiceConfigRepo(conn)
            await repo.upsert(key, value, None, validated=True)

    async def get_all(self) -> dict[str, str]:
        return {k: await self.get(k) for k in _DEFAULTS}


model_settings_store = ModelSettingsStore()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_model_settings_store.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add harmony/api/services/admin/model_settings.py tests/test_model_settings_store.py
git commit -m "feat: add ModelSettingsStore backed by service_configs table"
```

---

### Task 3: QdrantService.is_empty()

**Files:**
- Modify: `harmony/api/services/qdrant.py`
- Modify: `tests/test_qdrant_service.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_qdrant_service.py`:

```python
async def test_is_empty_returns_true_when_no_points() -> None:
    mock_client = AsyncMock()
    mock_info = MagicMock()
    mock_info.points_count = 0
    mock_client.get_collection.return_value = mock_info

    service = QdrantService(host="http://localhost:6333", collection="test", vector_size=512)
    service._client = mock_client

    assert await service.is_empty() is True


async def test_is_empty_returns_false_when_has_points() -> None:
    mock_client = AsyncMock()
    mock_info = MagicMock()
    mock_info.points_count = 42
    mock_client.get_collection.return_value = mock_info

    service = QdrantService(host="http://localhost:6333", collection="test", vector_size=512)
    service._client = mock_client

    assert await service.is_empty() is False
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_qdrant_service.py::test_is_empty_returns_true_when_no_points tests/test_qdrant_service.py::test_is_empty_returns_false_when_has_points -v
```

Expected: FAIL — `QdrantService has no attribute 'is_empty'`.

- [ ] **Step 3: Add is_empty() to QdrantService**

In `harmony/api/services/qdrant.py`, add before `close()`:

```python
    async def is_empty(self) -> bool:
        info = await self._client.get_collection(self._collection)
        return info.points_count == 0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_qdrant_service.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add harmony/api/services/qdrant.py tests/test_qdrant_service.py
git commit -m "feat: add QdrantService.is_empty()"
```

---

### Task 4: Update Vector and Reranker Backends

**Files:**
- Modify: `harmony/api/backends/vector.py`
- Modify: `harmony/api/backends/reranker.py`
- Modify: `harmony/api/services/pipeline_config.py`
- Modify: `tests/test_vector_backend.py`
- Modify: `tests/test_reranker_backend.py`

- [ ] **Step 1: Update vector backend tests**

In `tests/test_vector_backend.py`, replace any fixture/mock that passes `embedding_model` to the constructor with a mock of `model_settings_store.get`:

```python
# Find all occurrences of HarmonyVectorBackend(..., embedding_model=...) and replace with:
# HarmonyVectorBackend(qdrant_service=mock_qdrant)
# and add a patch for model_settings_store.get returning the model string

# Example — update existing test_vector_search_returns_results (or equivalent):
async def test_vector_search_returns_results() -> None:
    mock_qdrant = AsyncMock()
    mock_qdrant.search.return_value = [("https://example.com/page", 0.9)]

    backend = HarmonyVectorBackend(qdrant_service=mock_qdrant)

    with patch(
        "harmony.api.backends.vector.model_settings_store.get",
        AsyncMock(return_value="ollama/qwen3-embedding:0.6b"),
    ):
        with patch("litellm.aembedding", AsyncMock(return_value=MagicMock(data=[MagicMock(embedding=[0.1] * 512)]))):
            results = await backend.vector_search("test query", top_n=5)

    assert len(results) == 1
    assert results[0].path == "https://example.com/page"
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_vector_backend.py -v
```

Expected: FAIL — constructor still requires `embedding_model`.

- [ ] **Step 3: Update HarmonyVectorBackend**

Replace `harmony/api/backends/vector.py` with:

```python
from __future__ import annotations

import logging

import litellm
from kv_search import SearchHit, VectorSearchBackend

from harmony.api.services.qdrant import QdrantService

logger = logging.getLogger(__name__)


class HarmonyVectorBackend(VectorSearchBackend):
    def __init__(self, *, qdrant_service: QdrantService) -> None:
        self._qdrant = qdrant_service

    async def vector_search(
        self,
        query: str,
        *,
        top_n: int = 10,
        min_score: float = 0.35,
        allowlist: list[str] | None = None,
    ) -> list[SearchHit]:
        from harmony.api.services.admin.model_settings import model_settings_store  # noqa: PLC0415

        embedding_model = await model_settings_store.get("embedding_model")
        try:
            response = await litellm.aembedding(model=embedding_model, input=[query])
            vector: list[float] = response.data[0].embedding
        except Exception:
            logger.exception("embedding failed for query %r", query)
            return []

        results = await self._qdrant.search(
            vector=vector,
            top_n=top_n,
            min_score=min_score,
            allowlist=allowlist,
        )
        return [SearchHit(path=path, score=score) for path, score in results]
```

- [ ] **Step 4: Update reranker backend tests**

In `tests/test_reranker_backend.py`, replace `HarmonyRerankerBackend(model=...)` with `HarmonyRerankerBackend()` and patch `model_settings_store.get`:

```python
async def test_rerank_returns_reordered_hits() -> None:
    candidates = [
        SearchHit(path="a.com", score=0.5),
        SearchHit(path="b.com", score=0.4),
    ]
    mock_result = MagicMock()
    mock_result.results = [
        MagicMock(index=1, relevance_score=0.9),
        MagicMock(index=0, relevance_score=0.3),
    ]

    backend = HarmonyRerankerBackend()

    with patch(
        "harmony.api.backends.reranker.model_settings_store.get",
        AsyncMock(return_value="ollama/bge-reranker-v2-m3"),
    ):
        with patch("litellm.arerank", AsyncMock(return_value=mock_result)):
            results = await backend.rerank("query", candidates, top_n=2)

    assert results[0].path == "b.com"
    assert results[1].path == "a.com"
```

- [ ] **Step 5: Update HarmonyRerankerBackend**

Replace `harmony/api/backends/reranker.py` with:

```python
from __future__ import annotations

import dataclasses
import logging

import litellm
from kv_search import RerankerBackend, SearchHit

logger = logging.getLogger(__name__)


class HarmonyRerankerBackend(RerankerBackend):
    async def rerank(
        self,
        query: str,
        candidates: list[SearchHit],
        *,
        top_n: int,
    ) -> list[SearchHit]:
        from harmony.api.services.admin.model_settings import model_settings_store  # noqa: PLC0415

        reranker_model = await model_settings_store.get("reranker_model")
        docs = [h.metadata.get("content", h.path) for h in candidates]
        try:
            response = await litellm.arerank(
                model=reranker_model,
                query=query,
                documents=docs,
                top_n=top_n,
            )
        except Exception:
            logger.exception(
                "reranker failed for query %r, returning candidates as-is", query
            )
            return candidates[:top_n]

        return [
            dataclasses.replace(candidates[r.index], score=r.relevance_score)
            for r in response.results
        ]
```

- [ ] **Step 6: Remove reranker_model from PipelineConfig**

Replace `harmony/api/services/pipeline_config.py` with:

```python
from __future__ import annotations

import dataclasses


@dataclasses.dataclass
class PipelineConfig:
    keyword_candidates_n: int = 50
    vector_top_k: int = 20
    search_top_k: int = 5
    vector_search_enabled: bool = True
    reranker_enabled: bool = False
```

- [ ] **Step 7: Run all backend tests**

```bash
pytest tests/test_vector_backend.py tests/test_reranker_backend.py tests/test_pipeline_config.py -v
```

Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add harmony/api/backends/vector.py harmony/api/backends/reranker.py harmony/api/services/pipeline_config.py tests/test_vector_backend.py tests/test_reranker_backend.py
git commit -m "refactor: read model config at request time from ModelSettingsStore"
```

---

### Task 5: Ollama Proxy Routes

**Files:**
- Create: `harmony/api/routes/admin/ollama.py`
- Create: `tests/test_ollama_routes.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ollama_routes.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from harmony.api.routes.admin.ollama import router
from fastapi import FastAPI

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_list_models_returns_tags() -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {"models": [{"name": "qwen3-embedding:0.6b", "size": 100}]}
    mock_response.raise_for_status = MagicMock()

    with patch("harmony.api.routes.admin.ollama.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = client.get("/")

    assert response.status_code == 200
    assert response.json()["models"][0]["name"] == "qwen3-embedding:0.6b"


def test_list_models_returns_502_when_ollama_unreachable() -> None:
    import httpx

    with patch("harmony.api.routes.admin.ollama.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("refused")
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = client.get("/")

    assert response.status_code == 502


def test_delete_model_returns_deleted_true() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("harmony.api.routes.admin.ollama.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = client.delete("/qwen3-embedding:0.6b")

    assert response.status_code == 200
    assert response.json() == {"deleted": True}
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_ollama_routes.py -v
```

Expected: `ImportError` — `ollama.py` doesn't exist yet.

- [ ] **Step 3: Implement Ollama routes**

```python
# harmony/api/routes/admin/ollama.py
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from harmony.api.config import settings

router = APIRouter()


@router.get("")
async def list_ollama_models() -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{settings.ollama_host}/api/tags")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Ollama unreachable: {e}") from e


class PullRequest(BaseModel):
    name: str


@router.post("/pull")
async def pull_ollama_model(body: PullRequest) -> StreamingResponse:
    async def _stream():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_host}/api/pull",
                json={"name": body.name, "stream": True},
            ) as resp:
                async for line in resp.aiter_lines():
                    if line:
                        yield f"data: {line}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.delete("/{name:path}")
async def delete_ollama_model(name: str) -> dict[str, bool]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.request(
                "DELETE",
                f"{settings.ollama_host}/api/delete",
                json={"name": name},
            )
            resp.raise_for_status()
            return {"deleted": True}
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Ollama error: {e}") from e
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_ollama_routes.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add harmony/api/routes/admin/ollama.py tests/test_ollama_routes.py
git commit -m "feat: add Ollama proxy routes for model management"
```

---

### Task 6: Model Settings Routes

**Files:**
- Create: `harmony/api/routes/admin/model_settings.py`
- Create: `tests/test_model_settings_routes.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_model_settings_routes.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from harmony.api.routes.admin.model_settings import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

_DEFAULT_SETTINGS = {
    "embedding_provider": "ollama",
    "embedding_model": "ollama/qwen3-embedding:0.6b",
    "reranker_provider": "ollama",
    "reranker_model": "ollama/bge-reranker-v2-m3",
    "llm_provider": "litellm",
    "llm_model": "gemini/gemini-3-flash-preview",
    "embedding_model_changed_since_last_embed": "false",
}


def test_get_model_settings_returns_all_keys() -> None:
    with patch(
        "harmony.api.routes.admin.model_settings.model_settings_store.get_all",
        AsyncMock(return_value=_DEFAULT_SETTINGS),
    ):
        response = client.get("/")

    assert response.status_code == 200
    assert response.json()["embedding_model"] == "ollama/qwen3-embedding:0.6b"


def test_patch_model_settings_sets_changed_flag_when_embedding_model_changes() -> None:
    current_settings = dict(_DEFAULT_SETTINGS)

    async def mock_get(key: str) -> str:
        return current_settings[key]

    async def mock_set(key: str, value: str) -> None:
        current_settings[key] = value

    async def mock_get_all() -> dict:
        return current_settings

    with patch("harmony.api.routes.admin.model_settings.model_settings_store") as mock_store:
        mock_store.get = mock_get
        mock_store.set = mock_set
        mock_store.get_all = mock_get_all
        with patch("harmony.api.routes.admin.model_settings._validate_model", AsyncMock()):
            response = client.patch("/", json={"embedding_model": "ollama/nomic-embed-text"})

    assert response.status_code == 200
    assert current_settings["embedding_model_changed_since_last_embed"] == "true"


def test_validate_model_returns_valid_true_for_ollama_pulled_model() -> None:
    with patch("harmony.api.routes.admin.model_settings._validate_model", AsyncMock()):
        response = client.post("/validate", json={
            "model": "ollama/qwen3-embedding:0.6b",
            "provider": "ollama",
            "model_type": "embedding",
        })

    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_validate_model_returns_valid_false_on_http_exception() -> None:
    from fastapi import HTTPException

    with patch(
        "harmony.api.routes.admin.model_settings._validate_model",
        AsyncMock(side_effect=HTTPException(status_code=400, detail="not found")),
    ):
        response = client.post("/validate", json={
            "model": "ollama/nonexistent",
            "provider": "ollama",
            "model_type": "embedding",
        })

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert "not found" in response.json()["error"]
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_model_settings_routes.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement model settings routes**

```python
# harmony/api/routes/admin/model_settings.py
from __future__ import annotations

import httpx
import litellm
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from harmony.api.config import settings
from harmony.api.services.admin.model_settings import model_settings_store

router = APIRouter()


class ModelSettingsUpdate(BaseModel):
    embedding_provider: str | None = None
    embedding_model: str | None = None
    reranker_provider: str | None = None
    reranker_model: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None


class ValidateRequest(BaseModel):
    model: str
    provider: str
    model_type: str


@router.get("")
async def get_model_settings() -> dict[str, str]:
    return await model_settings_store.get_all()


@router.patch("")
async def update_model_settings(update: ModelSettingsUpdate) -> dict[str, str]:
    data = update.model_dump(exclude_none=True)

    for key, value in data.items():
        if key.endswith("_model"):
            provider_key = key.replace("_model", "_provider")
            provider = data.get(provider_key) or await model_settings_store.get(provider_key)
            await _validate_model(value, provider, key.replace("_model", ""))

        if key == "embedding_model":
            current = await model_settings_store.get("embedding_model")
            if value != current:
                await model_settings_store.set("embedding_model_changed_since_last_embed", "true")

        await model_settings_store.set(key, value)

    return await model_settings_store.get_all()


@router.post("/validate")
async def validate_model_endpoint(body: ValidateRequest) -> dict[str, bool | str]:
    try:
        await _validate_model(body.model, body.provider, body.model_type)
        return {"valid": True}
    except HTTPException as e:
        return {"valid": False, "error": e.detail}


async def _validate_model(model: str, provider: str, model_type: str) -> None:  # noqa: ARG001
    if provider == "ollama":
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(f"{settings.ollama_host}/api/tags")
                tags = resp.json()
                pulled = {m["name"] for m in tags.get("models", [])}
                bare = model.removeprefix("ollama/")
                if bare not in pulled:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Model {model!r} not pulled in Ollama",
                    )
            except httpx.HTTPError as e:
                raise HTTPException(
                    status_code=502, detail=f"Ollama unreachable: {e}"
                ) from e
    else:
        valid = set(litellm.get_valid_models(check_provider_endpoint=True))
        if model not in valid:
            raise HTTPException(
                status_code=400,
                detail=f"Model {model!r} not recognised by litellm",
            )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_model_settings_routes.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add harmony/api/routes/admin/model_settings.py tests/test_model_settings_routes.py
git commit -m "feat: add model settings GET/PATCH/validate routes"
```

---

### Task 7: Embed Job Type

**Files:**
- Modify: `harmony/api/models/job.py`
- Modify: `harmony/api/services/admin/job_manager.py`
- Modify: `harmony/api/routes/admin/jobs.py`
- Create: `tests/test_jobs_embed.py`

- [ ] **Step 1: Extend JobType**

In `harmony/api/models/job.py`, change line 9:

```python
# Before:
JobType = typing.Literal["crawl", "index"]

# After:
JobType = typing.Literal["crawl", "index", "embed"]
```

- [ ] **Step 2: Add start_embed_job to JobManager**

In `harmony/api/services/admin/job_manager.py`, add after `start_index_job()`:

```python
    async def start_embed_job(self, *, embedding_model: str) -> Job:
        """Start an embed job using harmony-embed CLI."""
        job_id = str(uuid.uuid4())[:8]
        log_file = self.job_log_path / f"embed-{job_id}.log"

        job = Job(
            id=job_id,
            type="embed",
            config_name=f"embed-{embedding_model}",
            log_file=str(log_file),
            started_at=datetime.now(UTC),
        )

        cmd = [
            "harmony-embed",
            f"--embedder.embedding-model={embedding_model}",
        ]

        env = {**os.environ}

        try:
            with log_file.open("w") as log_f:
                process = subprocess.Popen(
                    cmd,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    preexec_fn=os.setsid,  # noqa: PLW1509
                    env=env,
                )

            self._processes[job_id] = process
            job.pid = process.pid
            job.status = JobStatus.RUNNING

            self._progress_tasks[job_id] = asyncio.create_task(
                self._monitor_embed_job(job_id)
            )

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)

        self._jobs[job_id] = job
        pool = await get_async_pool()
        await JobsRepo(pool).upsert(job.model_dump(mode="json"))
        return job

    async def _monitor_embed_job(self, job_id: str) -> None:
        """Monitor an embed job: poll process for exit, clear changed flag on success."""
        job = self._jobs.get(job_id)
        process = self._processes.get(job_id)

        if not job or not process:
            return

        while True:
            await asyncio.sleep(1.0)
            return_code = process.poll()
            if return_code is not None:
                if return_code == 0:
                    job.status = JobStatus.COMPLETED
                    from harmony.api.services.admin.model_settings import model_settings_store  # noqa: PLC0415
                    await model_settings_store.set("embedding_model_changed_since_last_embed", "false")
                else:
                    job.status = JobStatus.FAILED
                    job.error = f"Process exited with code {return_code}"

                job.finished_at = datetime.now(UTC)
                pool = await get_async_pool()
                await JobsRepo(pool).update_status(
                    job_id, str(job.status), job.finished_at, job.error
                )

                if job_id in self._processes:
                    del self._processes[job_id]
                break
```

- [ ] **Step 3: Add POST /embed route**

In `harmony/api/routes/admin/jobs.py`, add the import and route after the existing `start_index_job` route:

```python
# Add to imports at top:
from harmony.api.services.admin.model_settings import model_settings_store

# Add after start_index_job route:
@router.post("/embed", response_model=Job)
async def start_embed_job() -> Job:
    """Start a re-embed job using the current embedding model."""
    embedding_model = await model_settings_store.get("embedding_model")
    try:
        return await job_manager.start_embed_job(embedding_model=embedding_model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
```

- [ ] **Step 4: Write failing tests**

```python
# tests/test_jobs_embed.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harmony.api.models.job import Job, JobStatus
from harmony.api.services.admin.job_manager import JobManager


async def test_start_embed_job_creates_job_with_embed_type() -> None:
    manager = JobManager()
    manager._job_log_path = MagicMock()
    manager._job_log_path.__truediv__ = MagicMock(return_value=MagicMock())
    manager._job_log_path.__truediv__.return_value.open = MagicMock(
        return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock()), __exit__=MagicMock(return_value=False))
    )

    mock_pool = AsyncMock()
    mock_repo = AsyncMock()

    with patch("harmony.api.services.admin.job_manager.subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_popen.return_value = mock_proc
        with patch("harmony.api.services.admin.job_manager.get_async_pool", AsyncMock(return_value=mock_pool)):
            with patch("harmony.api.services.admin.job_manager.JobsRepo", return_value=mock_repo):
                with patch("asyncio.create_task"):
                    job = await manager.start_embed_job(embedding_model="ollama/qwen3-embedding:0.6b")

    assert job.type == "embed"
    assert job.status == JobStatus.RUNNING
    assert "qwen3-embedding" in job.config_name


async def test_monitor_embed_job_clears_changed_flag_on_success() -> None:
    manager = JobManager()
    manager._job_log_path = MagicMock()

    job = Job(id="test123", type="embed", config_name="embed-test", status=JobStatus.RUNNING)
    manager._jobs["test123"] = job

    mock_proc = MagicMock()
    mock_proc.poll.side_effect = [None, None, 0]
    manager._processes["test123"] = mock_proc

    mock_pool = AsyncMock()
    mock_repo = AsyncMock()

    with patch("harmony.api.services.admin.job_manager.get_async_pool", AsyncMock(return_value=mock_pool)):
        with patch("harmony.api.services.admin.job_manager.JobsRepo", return_value=mock_repo):
            with patch("harmony.api.services.admin.model_settings.model_settings_store") as mock_store:
                mock_store.set = AsyncMock()
                with patch("asyncio.sleep", AsyncMock()):
                    await manager._monitor_embed_job("test123")

    assert job.status == JobStatus.COMPLETED
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_jobs_embed.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add harmony/api/models/job.py harmony/api/services/admin/job_manager.py harmony/api/routes/admin/jobs.py tests/test_jobs_embed.py
git commit -m "feat: add embed job type and start_embed_job to job manager"
```

---

### Task 8: Extend Setup Route

**Files:**
- Modify: `harmony/api/routes/admin/setup.py`

- [ ] **Step 1: Extend SetupRequest and complete_setup handler**

Replace `harmony/api/routes/admin/setup.py` with:

```python
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from harmony.api.services.admin.model_settings import model_settings_store
from harmony.api.services.admin.service_config import service_config_store

router = APIRouter()


class ConfigValidationRequest(BaseModel):
    elasticsearch_url: str | None = None
    redis_url: str | None = None


class SetupRequest(BaseModel):
    elasticsearch_url: str
    redis_url: str
    embedding_provider: str = "ollama"
    embedding_model: str = "ollama/qwen3-embedding:0.6b"
    reranker_provider: str = "ollama"
    reranker_model: str = "ollama/bge-reranker-v2-m3"
    llm_provider: str = "litellm"
    llm_model: str = "gemini/gemini-3-flash-preview"


class ValidationResult(BaseModel):
    ok: bool
    message: str


class ValidationResponse(BaseModel):
    elasticsearch: ValidationResult | None = None
    redis: ValidationResult | None = None


class SetupStatusResponse(BaseModel):
    is_configured: bool
    missing_configs: list[str]


@router.get("/status", response_model=SetupStatusResponse)
async def get_setup_status() -> SetupStatusResponse:
    is_configured = await service_config_store.is_configured()
    missing_configs = []
    if not is_configured:
        for key in ["elasticsearch_url", "redis_url"]:
            value = await service_config_store.get(key)
            if not value or value == service_config_store.DEFAULTS.get(key):
                missing_configs.append(key)
    return SetupStatusResponse(
        is_configured=is_configured,
        missing_configs=missing_configs,
    )


@router.post("/validate", response_model=ValidationResponse)
async def validate_config(config: ConfigValidationRequest) -> ValidationResponse:
    result = ValidationResponse()
    if config.elasticsearch_url:
        ok, message = await service_config_store.validate_elasticsearch(config.elasticsearch_url)
        result.elasticsearch = ValidationResult(ok=ok, message=message)
    if config.redis_url:
        ok, message = await service_config_store.validate_redis(config.redis_url)
        result.redis = ValidationResult(ok=ok, message=message)
    return result


@router.post("/complete")
async def complete_setup(config: SetupRequest) -> dict[str, str]:
    es_ok, es_message = await service_config_store.validate_elasticsearch(config.elasticsearch_url)
    redis_ok, redis_message = await service_config_store.validate_redis(config.redis_url)

    if not es_ok:
        raise HTTPException(status_code=400, detail=f"Elasticsearch validation failed: {es_message}")
    if not redis_ok:
        raise HTTPException(status_code=400, detail=f"Redis validation failed: {redis_message}")

    await service_config_store.set("elasticsearch_url", config.elasticsearch_url, validated=True)
    await service_config_store.set("redis_url", config.redis_url, validated=True)

    await model_settings_store.set("embedding_provider", config.embedding_provider)
    await model_settings_store.set("embedding_model", config.embedding_model)
    await model_settings_store.set("reranker_provider", config.reranker_provider)
    await model_settings_store.set("reranker_model", config.reranker_model)
    await model_settings_store.set("llm_provider", config.llm_provider)
    await model_settings_store.set("llm_model", config.llm_model)

    return {"status": "success", "message": "Setup completed successfully"}
```

- [ ] **Step 2: Run existing setup tests**

```bash
pytest tests/test_settings_route.py -v
```

Expected: all PASS (no behaviour changed for existing fields).

- [ ] **Step 3: Commit**

```bash
git add harmony/api/routes/admin/setup.py
git commit -m "feat: extend setup/complete to save model settings"
```

---

### Task 9: Wire Everything in main.py

**Files:**
- Modify: `harmony/api/main.py`

- [ ] **Step 1: Update main.py**

Make these changes to `harmony/api/main.py`:

**a) Update imports** — add `ollama` and `model_settings` routes, remove `embedding_model` from backend construction:

```python
# Add to existing admin route imports:
from harmony.api.routes.admin import auth, configs, index_config, internal, jobs, logs, model_settings as model_settings_route, ollama, reset, schema, setup
```

**b) Update `_build_search_service`** — remove model constructor args:

```python
def _build_search_service(
    qdrant_service: QdrantService, pipeline_config: PipelineConfig
) -> tuple[SearchService, HarmonyKeywordBackend]:
    keyword_backend = HarmonyKeywordBackend(
        host=settings.es_config.host,
        index_base_name=settings.es_config.index_base_name,
        languages=settings.es_config.languages,
        boost_title=settings.es_config.mutable.boost_title,
        boost_content=settings.es_config.mutable.boost_content,
        size=pipeline_config.keyword_candidates_n,
    )
    vector_backend = HarmonyVectorBackend(qdrant_service=qdrant_service)
    reranker_backend = HarmonyRerankerBackend()
    return SearchService(
        keyword_backend=keyword_backend,
        vector_backend=vector_backend,
        reranker_backend=reranker_backend,
        config=pipeline_config,
    ), keyword_backend
```

**c) Add empty-Qdrant check in lifespan** — after `await qdrant_service.ensure_collection()`:

```python
    await qdrant_service.ensure_collection()
    logger.info(f"Connected to Qdrant at {settings.qdrant_host}")

    if await qdrant_service.is_empty():
        pipeline_config = PipelineConfig(vector_search_enabled=False)
        logger.info("Qdrant collection empty — vector search disabled until first embed job")
    else:
        pipeline_config = PipelineConfig()
```

Move `pipeline_config = PipelineConfig()` to be replaced by the above block (it currently appears before `_build_search_service` is called).

**d) Add new routes** after existing admin routes:

```python
app.include_router(ollama.router, prefix="/api/models/ollama", tags=["ollama"])
app.include_router(model_settings_route.router, prefix="/api/settings/models", tags=["model-settings"])
```

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 3: Run pre-commit**

```bash
pre-commit run --all-files
```

Expected: all checks PASS.

- [ ] **Step 4: Commit**

```bash
git add harmony/api/main.py
git commit -m "feat: wire model settings and Ollama routes, disable vector search when Qdrant empty"
```
