# Data Models

Data models are not centralized — they're spread across ~30 files in three layers with different lifetimes. Don't hand-maintain a list here; it goes stale immediately. Instead:

```bash
python .claude/scripts/find_data_models.py          # scans harmony/ by default
python .claude/scripts/find_data_models.py harmony/api/routes
```

This walks the AST for every `@dataclass`, `pydantic.BaseModel` subclass, and `TypedDict` and prints `file:line ClassName`. Run it before assuming a model exists at a remembered path, and re-run after any refactor that moves files. As of the last audit: 100 BaseModels, 69 dataclasses, 9 TypedDicts (178 total).

For graph-based queries (callers, references, impact of changing a model), prefer `codebase-memory-mcp`'s `search_graph`/`trace_path` over grepping — see [[reference_codebase_memory_index]].

## The three layers

**1. Shared domain models — `harmony/models/`** (top-level, facade via `__init__.py`)
The "centralized" cross-cutting model location: `_user.py` (`UserIdentity`, `AnonymousIdentity`), `_job.py`, `_search.py` (`Source`), `_status.py` (SSE status TypedDicts + `status_event_to_wire`/`lean_sources_for_trace` helpers). Import via the package facade (`from harmony.models import ...`), not the `_`-prefixed submodule. If a domain type needs to be imported by more than one route/service, it belongs here, not inline.

**2. Route-local request/response schemas — `harmony/api/routes/**.py`**
Most `BaseModel` subclasses are defined inline in the route file that uses them (request bodies, response envelopes specific to one endpoint). This is intentional — these are HTTP contract types, not domain models, and don't need to be shared. Don't promote one to `harmony/models/` unless a second route needs it.

**3. Internal/write-layer dataclasses — `harmony/db/repositories/*.py`, services, agents**
Dataclasses used for internal state or as write-DTOs into the repository layer (e.g. `ModelCreateData`, `ModelRegistryRow`). Row DTOs live in `harmony/db/models.py` (imported by both repositories and services via the `harmony.db.repositories` facade); write-DTOs and service-internal state stay next to the code that uses them. These are implementation details, not part of the API contract.

## Persisted schema

The actual table shape is defined by Alembic migrations (`alembic/versions/`, 27+ files), not by any Python class — the dataclasses/BaseModels above are read/write views over it. For current table structure, read the latest migration touching that table, don't infer it from a dataclass.
