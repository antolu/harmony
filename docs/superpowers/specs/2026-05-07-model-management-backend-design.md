# Model Management Backend Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add runtime-mutable model settings (embedding model, reranker model, LLM model) backed by PostgreSQL, Ollama proxy routes, a re-embed job type, and update the vector/reranker backends to read model config at request time rather than construction time.

**Architecture:** Model settings are stored as key-value rows in the existing `service_configs` table (same pattern as `ServiceConfigStore`). A new `ModelSettingsStore` reads from DB with ENV → DB → DEFAULT priority. Both `HarmonyVectorBackend` and `HarmonyRerankerBackend` drop their constructor model args and read from `ModelSettingsStore` at request time. Ollama model management is proxied through three new backend routes.

**Tech Stack:** Python 3.13, FastAPI, psycopg (async), Alembic, litellm, httpx (async Ollama proxy)

---

## Database

### Migration `0004_add_model_settings.py`

Inserts default rows into the existing `service_configs` table:

```sql
INSERT INTO service_configs (key, value, description, is_configured)
VALUES
  ('embedding_provider', 'ollama', 'Provider for embedding model: ollama or litellm', true),
  ('embedding_model', 'ollama/qwen3-embedding:0.6b', 'litellm model string for embeddings', true),
  ('reranker_provider', 'ollama', 'Provider for reranker model: ollama or litellm', true),
  ('reranker_model', 'ollama/bge-reranker-v2-m3', 'litellm model string for reranking', true),
  ('llm_provider', 'litellm', 'Provider for LLM: ollama or litellm', true),
  ('llm_model', 'gemini/gemini-3-flash-preview', 'litellm model string for LLM', true),
  ('embedding_model_changed_since_last_embed', 'false', 'Set true when embedding model changes, cleared on successful embed job', true)
ON CONFLICT (key) DO NOTHING;
```

No new table needed — `service_configs` is a generic key-value store.

---

## New Files

### `harmony/api/services/admin/model_settings.py`

`ModelSettingsStore` — thin wrapper over `ServiceConfigRepo` for model-specific keys. Same ENV → DB → DEFAULT priority as `ServiceConfigStore`.

```python
from __future__ import annotations

from harmony.api.config import settings as app_settings
from harmony.api.services.pipeline_config import PipelineConfig
from harmony.db.repositories import ServiceConfigRepo

_DEFAULTS: dict[str, str] = {
    "embedding_provider": "ollama",
    "embedding_model": app_settings.embedding_model,
    "reranker_provider": "ollama",
    "reranker_model": PipelineConfig.reranker_model,
    "llm_provider": "litellm",
    "llm_model": app_settings.llm_model,
    "embedding_model_changed_since_last_embed": "false",
}

_ENV_MAP: dict[str, str | None] = {
    "embedding_model": app_settings.embedding_model,
    "reranker_model": None,
    "llm_model": app_settings.llm_model,
    "embedding_provider": None,
    "reranker_provider": None,
    "llm_provider": None,
    "embedding_model_changed_since_last_embed": None,
}


class ModelSettingsStore:
    async def get(self, key: str) -> str:
        env_val = _ENV_MAP.get(key)
        if env_val:
            return env_val
        from harmony.db.connection import get_async_pool  # noqa: PLC0415
        pool = await get_async_pool()
        async with pool.connection() as conn:
            repo = ServiceConfigRepo(conn)
            row = await repo.get(key)
            if row:
                return row["value"]
        return _DEFAULTS[key]

    async def set(self, key: str, value: str) -> None:
        from harmony.db.connection import get_async_pool  # noqa: PLC0415
        pool = await get_async_pool()
        async with pool.connection() as conn:
            repo = ServiceConfigRepo(conn)
            await repo.set(key, value)

    async def get_all(self) -> dict[str, str]:
        return {k: await self.get(k) for k in _DEFAULTS}


model_settings_store = ModelSettingsStore()
```

### `harmony/api/routes/admin/ollama.py`

Proxy routes for Ollama model management. Uses `settings.ollama_host` for the Ollama URL.

```python
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


class DeleteRequest(BaseModel):
    name: str


@router.delete("/{name}")
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

### `harmony/api/routes/admin/model_settings.py`

```python
from __future__ import annotations

import httpx
import litellm
from fastapi import APIRouter, HTTPException, Request
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
    model_type: str  # "embedding" | "reranker" | "llm"


@router.get("")
async def get_model_settings() -> dict[str, str]:
    return await model_settings_store.get_all()


@router.patch("")
async def update_model_settings(update: ModelSettingsUpdate) -> dict[str, str]:
    data = update.model_dump(exclude_none=True)

    for key, value in data.items():
        provider_key = key.replace("_model", "_provider")
        provider = data.get(provider_key) or await model_settings_store.get(provider_key)

        if key.endswith("_model"):
            await _validate_model(value, provider, key.replace("_model", ""))

        if key == "embedding_model":
            current = await model_settings_store.get("embedding_model")
            if value != current:
                await model_settings_store.set("embedding_model_changed_since_last_embed", "true")

        await model_settings_store.set(key, value)

    return await model_settings_store.get_all()


@router.post("/validate")
async def validate_model(body: ValidateRequest) -> dict[str, bool | str]:
    try:
        await _validate_model(body.model, body.provider, body.model_type)
        return {"valid": True}
    except HTTPException as e:
        return {"valid": False, "error": e.detail}


async def _validate_model(model: str, provider: str, model_type: str) -> None:
    if provider == "ollama":
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(f"{settings.ollama_host}/api/tags")
                tags = resp.json()
                pulled = {m["name"] for m in tags.get("models", [])}
                if model.removeprefix("ollama/") not in pulled:
                    raise HTTPException(status_code=400, detail=f"Model {model!r} not pulled in Ollama")
            except httpx.HTTPError as e:
                raise HTTPException(status_code=502, detail=f"Ollama unreachable: {e}") from e
    else:
        valid = set(litellm.get_valid_models(check_provider_endpoint=True))
        if model not in valid:
            raise HTTPException(status_code=400, detail=f"Model {model!r} not recognised by litellm")
```

---

## Modified Files

### `harmony/api/backends/vector.py`

Remove `embedding_model` constructor arg. Read from `model_settings_store` at request time.

```python
# Before:
class HarmonyVectorBackend(VectorSearchBackend):
    def __init__(self, *, qdrant_service: QdrantService, embedding_model: str) -> None:
        self._qdrant_service = qdrant_service
        self._embedding_model = embedding_model

    async def vector_search(self, query: str, ...) -> list[SearchHit]:
        embedding = await litellm.aembedding(model=self._embedding_model, input=[query])
        ...

# After:
class HarmonyVectorBackend(VectorSearchBackend):
    def __init__(self, *, qdrant_service: QdrantService) -> None:
        self._qdrant_service = qdrant_service

    async def vector_search(self, query: str, ...) -> list[SearchHit]:
        from harmony.api.services.admin.model_settings import model_settings_store  # noqa: PLC0415
        embedding_model = await model_settings_store.get("embedding_model")
        embedding = await litellm.aembedding(model=embedding_model, input=[query])
        ...
```

### `harmony/api/backends/reranker.py`

Same change — remove `model` constructor arg, read from `model_settings_store` at request time.

```python
# After:
class HarmonyRerankerBackend(RerankerBackend):
    async def rerank(self, query: str, candidates: list[SearchHit], *, top_n: int) -> list[SearchHit]:
        from harmony.api.services.admin.model_settings import model_settings_store  # noqa: PLC0415
        reranker_model = await model_settings_store.get("reranker_model")
        try:
            response = await litellm.arerank(model=reranker_model, query=query, documents=docs, top_n=top_n)
        except Exception:
            logger.exception("reranker failed for query %r, returning candidates as-is", query)
            return candidates[:top_n]
        return [dataclasses.replace(candidates[r.index], score=r.relevance_score) for r in response.results]
```

### `harmony/api/services/pipeline_config.py`

Remove `reranker_model` field — it now lives in `ModelSettingsStore`.

```python
@dataclasses.dataclass
class PipelineConfig:
    keyword_candidates_n: int = 50
    vector_top_k: int = 20
    search_top_k: int = 5
    vector_search_enabled: bool = True
    reranker_enabled: bool = False
    # reranker_model removed — now in ModelSettingsStore
```

### `harmony/api/main.py`

- Remove `embedding_model` from `HarmonyVectorBackend` constructor call
- Remove `model` from `HarmonyRerankerBackend` constructor call
- Add `model_settings_store.initialize()` (if needed) in lifespan
- Add Ollama and model settings routes
- On startup: if Qdrant collection is empty, force `pipeline_config.vector_search_enabled = False`

```python
# _build_search_service after change:
def _build_search_service(
    qdrant_service: QdrantService, pipeline_config: PipelineConfig
) -> tuple[SearchService, HarmonyKeywordBackend]:
    keyword_backend = HarmonyKeywordBackend(...)
    vector_backend = HarmonyVectorBackend(qdrant_service=qdrant_service)
    reranker_backend = HarmonyRerankerBackend()
    return SearchService(...), keyword_backend

# In lifespan, after qdrant_service.ensure_collection():
if await qdrant_service.is_empty():
    pipeline_config.vector_search_enabled = False
    logger.info("Qdrant collection empty — vector search disabled until first embed job")
```

Add to router registrations:
```python
app.include_router(ollama.router, prefix="/api/models/ollama", tags=["ollama"])
app.include_router(model_settings.router, prefix="/api/settings/models", tags=["model-settings"])
```

### `harmony/api/services/qdrant.py`

Add `is_empty()` method:

```python
async def is_empty(self) -> bool:
    info = await self._client.get_collection(self._collection)
    return info.points_count == 0
```

### `harmony/api/routes/admin/jobs.py`

Add `embed` job type. Extend `POST /api/jobs` or add `POST /api/jobs/embed`:

```python
@router.post("/embed")
async def start_embed_job() -> Job:
    embedding_model = await model_settings_store.get("embedding_model")
    job = await job_manager.start_embed_job(embedding_model=embedding_model)
    return job
```

### `harmony/api/services/admin/job_manager.py`

Add `start_embed_job()` that invokes `harmony-embed` CLI as a subprocess, same pattern as crawl/index jobs. On job completion (exit code 0), sets `embedding_model_changed_since_last_embed = false` in model settings store.

Extend the `jobs` table CHECK constraint on `type` to include `'embed'` — requires a new migration `0004` (or include in the same migration as the service_configs inserts above).

### `harmony/api/routes/admin/setup.py`

Extend `POST /setup/complete` to accept optional model settings:

```python
class SetupCompleteRequest(BaseModel):
    elasticsearch_url: str
    redis_url: str
    embedding_provider: str = "ollama"
    embedding_model: str = "ollama/qwen3-embedding:0.6b"
    reranker_provider: str = "ollama"
    reranker_model: str = "ollama/bge-reranker-v2-m3"
    llm_provider: str = "litellm"
    llm_model: str = "gemini/gemini-3-flash-preview"
```

On completion, saves model settings via `model_settings_store.set()` for each field.

---

## Database Migration: `0004_add_model_and_embed_job.py`

```python
def upgrade() -> None:
    # Extend jobs type check to include 'embed'
    op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS ck_jobs_type")
    op.execute(
        "ALTER TABLE jobs ADD CONSTRAINT ck_jobs_type "
        "CHECK (type IN ('crawl', 'index', 'embed'))"
    )

    # Seed model settings defaults into service_configs
    op.execute("""
        INSERT INTO service_configs (key, value, description, is_configured)
        VALUES
          ('embedding_provider', 'ollama', 'Provider for embedding model', true),
          ('embedding_model', 'ollama/qwen3-embedding:0.6b', 'litellm model string for embeddings', true),
          ('reranker_provider', 'ollama', 'Provider for reranker model', true),
          ('reranker_model', 'ollama/bge-reranker-v2-m3', 'litellm model string for reranking', true),
          ('llm_provider', 'litellm', 'Provider for LLM', true),
          ('llm_model', 'gemini/gemini-3-flash-preview', 'litellm model string for LLM', true),
          ('embedding_model_changed_since_last_embed', 'false', 'Cleared after successful embed job', true)
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

---

## Testing

- `tests/test_model_settings_store.py` — unit tests for `ModelSettingsStore.get()` priority chain (ENV > DB > DEFAULT), `set()`, `get_all()`
- `tests/test_ollama_routes.py` — mock httpx responses for list/pull/delete; verify SSE stream forwarding for pull
- `tests/test_model_settings_routes.py` — PATCH validation logic: Ollama provider checks pulled list, LiteLLM calls `get_valid_models`; embedding model change sets `changed` flag
- `tests/test_vector_backend.py` — update existing tests: mock `model_settings_store.get()` instead of constructor arg
- `tests/test_reranker_backend.py` — same
- `tests/test_jobs_embed.py` — POST /api/jobs/embed starts job, completion clears `embedding_model_changed_since_last_embed`
