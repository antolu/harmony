# Architecture

File-by-file layout goes stale fast — don't trust a hand-written file list, including this one if it's old. For current structure, use `codebase-memory-mcp`'s `get_architecture` (project overview), `search_graph` (find a function/class/route by name), or `search_code` (text search). Re-index after any significant refactor — see [[reference_codebase_memory_index]].

What follows are architectural *decisions* — things that don't show up from reading one file in isolation, and don't change just because a file gets renamed or moved.

## High-Level Flow

```
User Query → Harmony API
                  ↓
            ┌─────┴─────────────────────┐
            │   LLM Orchestration       │
            │   (Direct/AI/Agentic)     │
            └─────┬─────────────────────┘
                  ↓
            SearchService
            (three-stage pipeline)
           /              \
  Elasticsearch           Qdrant
  BM25 recall             vector re-rank
  (N candidates)          (filtered to keyword allowlist)
                                |
                          Reranker (opt-in)
                          litellm.arerank, bge-reranker-v2-m3
```

There is a **single FastAPI app** (`harmony.api.main:app`, port 8000) serving both search/chat endpoints and all admin functionality (`/api/admin/*`). The admin frontend (`frontend/`) is a separate Vite/React app, proxying to port 8000 in dev.

## Provider plugin pattern

Crawling and ingestion are pluggable providers, not a hardcoded crawler — `BaseProvider` defines the interface (`config_schema()` for JSON-schema config, `run()` returns job specs for subprocess execution). Built-ins are loaded by name from a registry; third-party providers register via Python entry points. When adding a new ingestion source, implement `BaseProvider` rather than special-casing it elsewhere. Don't assume a single top-level "crawler" package — search the graph for `BaseProvider` subclasses to find current providers.

## Module naming convention

Internal modules are prefixed with `_` (e.g. `_search.py`, `_base.py`) to mark them package-private; only re-exports in `__init__.py` and route/CLI entry files are unprefixed. This is pervasive across `agents/`, `backends/`, `services/`, `tools/`, `db/repositories/`. When a remembered import path 404s, try the `_`-prefixed version before assuming the module was deleted.

## Agentic search flow

```
1. QueryPlannerAgent → query variants (streamed)
2. SearcherAgent (parallel) → search results per variant (streamed)
3. K-Round Refinement Loop:
   - SynthesizerAgent → draft answer
   - CriticAgent → critique (checks consensus)
   - exit loop on consensus, else improve draft with critique
4. Final answer (streamed) + sources + citations
```

This is a Federation-of-Agents pattern: each agent has one responsibility, the orchestrator coordinates, and the searcher never touches ES/Qdrant directly — only through SearchService.

## Streaming

All search endpoints return SSE, not plain JSON responses. Event types: `query_variant`, `reading_page`, `refinement_round`, `answer_chunk`, `tool_call`, `done`, `error`. A new streaming endpoint should follow this same event vocabulary rather than inventing new event names — see [[patterns]] for the implementation pattern.

## Crawler safety (defense-in-depth)

Multiple independent layers, not one check: LinkExtractor deny patterns at extraction time, a runtime SafetyMiddleware, GET/HEAD-only HTTP method restriction, optional interactive allow/deny list building, and persisted patterns (`.harmony-safety-lists.json`). Never disable one layer assuming another covers it. Test new crawl targets with `--crawler.dry_run` first; use `--crawler.safe_mode` for unknown sites.

## Database layer

**Postgres** is the primary persistent store (jobs, schedules, audit log, webhooks, model registry, users, conversations, crawl blacklist, search query log), schema managed by Alembic — the migrations are the source of truth for table shape, not any Python class. The query layer is a *package* of thin async wrappers over raw `psycopg` (no ORM), split by domain — don't assume a single `repositories.py` file.

**Redis** holds session tokens for crawler auth and API key caching only — it is not a general cache layer.

## Auth

`JWTAuthMiddleware` intercepts every request and attaches identity to `request.state.user` as `UserIdentity | AnonymousIdentity`. Two auth paths exist side by side: API key (SHA256 lookup) and OIDC/SSO (Keycloak by default) — a route doesn't need to know which one authenticated the caller. `AUTH_MODE` controls whether anonymous access is allowed. Authorization (role checks) is a separate layer from authentication — see [[patterns]] for `require_role`.

## Admin frontend conventions

React Query for all server state, shadcn/ui (Radix + Tailwind) for components, React Router for navigation. New admin features need three pieces in lockstep: a route module under `admin/`, its router registered in `main.py`, and a frontend page+route — missing one of the three is the most common integration gap.
