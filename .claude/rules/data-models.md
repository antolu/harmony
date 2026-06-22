# Data Models

Data models are not centralized — they're spread across ~30 files in three layers with different lifetimes. Don't hand-maintain a list here; it goes stale immediately. Instead:

```bash
python .claude/scripts/find_data_models.py          # scans harmony/ by default
python .claude/scripts/find_data_models.py harmony/api/routes
```

This walks the AST for every `@dataclass`, `pydantic.BaseModel` subclass, and `TypedDict` and prints `file:line ClassName`. Run it before assuming a model exists at a remembered path, and re-run after any refactor that moves files. As of the last audit: 93 BaseModels, 59 dataclasses, 6 TypedDicts (158 total).

For graph-based queries (callers, references, impact of changing a model), prefer `codebase-memory-mcp`'s `search_graph`/`trace_path` over grepping — see [[reference_codebase_memory_index]].

## The three layers

**1. Shared domain models — `harmony/api/models/`**
The only "centralized" model location. Cross-cutting types referenced from multiple routes/services: `config.py` (ConfigEntry, ConfigListResponse, ConfigSaveRequest, ConfigImportRequest), `job.py`, `registry.py` (e.g. `ModelRegistryRow`, `ModelType`), `user.py` (`UserIdentity`, `AnonymousIdentity`). If a model needs to be imported by more than one route file, it belongs here, not inline in a route.

**2. Route-local request/response schemas — `harmony/api/routes/**.py`**
Most `BaseModel` subclasses are defined inline in the route file that uses them (request bodies, response envelopes specific to one endpoint). This is intentional — these are HTTP contract types, not domain models, and don't need to be shared. Don't promote one to `api/models/` unless a second route needs it.

**3. Internal/write-layer dataclasses — `harmony/db/repositories/*.py`, services, agents**
Dataclasses used for internal state or as write-DTOs into the repository layer (e.g. `ModelCreateData` in `harmony/db/repositories/_models.py`, which references back to `ModelRegistryRow` in `api/models/registry.py`). These are implementation details of a service or repository, not part of the API contract — keep them next to the code that uses them.

## Persisted schema

The actual table shape is defined by Alembic migrations (`alembic/versions/`, 27+ files), not by any Python class — the dataclasses/BaseModels above are read/write views over it. For current table structure, read the latest migration touching that table, don't infer it from a dataclass.
