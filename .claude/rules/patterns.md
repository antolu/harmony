# Service & Development Patterns

These are conventions to follow when adding code, not a map of existing files — file paths drift; search the graph (`search_graph`/`get_architecture`, see [[architecture]]) to find the current location of a base class before importing it.

## Service lifecycle: `app.state` + `dependencies.py`

All services are instantiated once at startup and stored on `app.state`. The `lifespan` in `main.py` is a thin composition root: it calls the `init_*` functions in the `harmony/api/_bootstrap/` package (one module per concern — `_db`, `_storage`, `_core`, `_search`, `_admin`, `_auth`, `_tools`, `_orchestrator`, plus `_maintenance` for nightly jobs), each returning a frozen dataclass of the services it built, then assembles them into `AppState`. Add a new startup service to the relevant `_bootstrap` module and its container dataclass, not inline in `main.py`. Routes never import services directly — they receive them through FastAPI `Depends()` functions defined in `harmony/api/dependencies.py`. Every `get_*` dependency just reads from `request.app.state`.

```python
def get_job_manager(request: Request) -> JobManager:
    return request.app.state.job_manager

@router.post("/jobs")
async def create_job(job_manager: JobManager = Depends(get_job_manager)):
    ...
```

Two singleton styles coexist: a few services are module-level singletons (instantiated at import time, then `.initialize()`d in lifespan), most are instantiated fresh inside lifespan and only exist on `app.state`. Don't add new module-level singletons — prefer instantiating in lifespan.

## Config resolution: ENV > DB > default

Runtime-mutable settings (OIDC URLs, pipeline tuning, API keys, auth mode) go through a config-store service that resolves: environment variable → Postgres-backed setting → hardcoded default. Don't read `os.environ` directly for anything that's supposed to be admin-configurable at runtime — route it through that store so the DB override and the env override both work.

## Job execution: subprocess, not async task

Long-running crawl/index jobs run as actual subprocesses, not asyncio tasks — this isolates crashes and lets jobs survive an API process restart. Each job writes output to a log file and publishes real-time stats to Redis pub/sub for the frontend to subscribe to; job state itself is persisted in Postgres, not just in-memory. If you add a new long-running operation, follow this subprocess + Redis-stream + Postgres-state shape rather than spawning an `asyncio.create_task`.

## Repository layer: no ORM

Repositories are thin async wrappers over raw parameterized `psycopg` queries, organized as one file per domain area, not one God file. Add new queries next to the domain they belong to; don't write SQL in routes or services directly. See [[data-models]] for how repository-layer dataclasses relate to shared domain models in `api/models/`.

## Observability: trace ID propagation

A middleware attaches a `trace_id` to every request and binds it into the structured-logging context, so every log line within a request automatically carries it without explicit threading. A separate LLM-usage callback intercepts every completion call and queues usage events for async batch writes to Postgres — don't add a second ad-hoc usage-tracking path; extend the existing callback.

## Authorization: role hierarchy

A `require_role(role)` dependency enforces a minimum role level (`admin > operator > read-only`) and is composed via FastAPI's `dependencies=[...]` on the route, not checked manually inside the handler body:

```python
@router.post("/jobs", dependencies=[Depends(require_role("operator"))])
async def create_job(...):
    ...
```

## Adding a new agent / tool / route

The shape is the same for all three: create the file in the relevant package (agent/tool/route), then explicitly register it — agents in the orchestrator, tools via `tool_registry.register(...)` in lifespan, routes via `app.include_router(...)` in `main.py`. Nothing is auto-discovered; forgetting the registration step is the most common reason a new agent/tool/route "doesn't show up."

```python
from __future__ import annotations

@tool
async def my_tool(param: str) -> str:
    """Tool description for LLM."""
    return result
```

## Streaming responses

Use `EventSourceResponse` from `sse_starlette` and yield dicts with `event`/`data` keys; reuse the existing event vocabulary (see [[architecture]]) rather than inventing new event names per endpoint.

```python
async def event_generator():
    yield {"event": "answer_chunk", "data": json.dumps({"chunk": token})}
    yield {"event": "done", "data": json.dumps({"sources": [...]})}

@router.post("/my-search")
async def my_search(request: SearchRequest):
    return EventSourceResponse(event_generator())
```

## Prompt templates

Prompts are Jinja2-templated `.md` files under `harmony/prompts/{system,user}/`, not inline strings — rendered via `PromptManager` (`harmony/api/services/_prompts.py`), injected the same way as other services (`app.state.prompt_manager`, `Depends(get_prompt_manager)`). Agents typically call the `render_system_prompt(name)` / `render_user_prompt(name, variables=...)` convenience wrappers rather than the lower-level `render(template_name, variables=...)`. Keep prompt text out of Python source so non-engineers can review/edit it.

## Writing tests

Mark tests that need external services rather than mocking them away by default: `@pytest.mark.llm` for real LLM calls, `@pytest.mark.elasticsearch` for ES, `@pytest.mark.integration` for full-stack. Default `pytest tests/` runs unit tests only — this is intentional, not a gap.
