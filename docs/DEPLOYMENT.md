# Deployment

Harmony is deployed via Docker Compose today. Kubernetes is on the [roadmap](../README.md#future) but not yet implemented — `docker-compose.yml` is the only supported production target.

This doc covers what infra needs to know to deploy Harmony outside the bundled `docker-compose.dev.yml` dev setup: required services, required vs. optional configuration, secrets, and production-specific settings.

## Required Services

| Service | Minimum version | Required? |
|---------|-----------------|------------|
| PostgreSQL | 17+ | Always — jobs, schedules, audit log, model registry, users, conversations |
| Redis | 7+ | Always — pub/sub, crawler-auth session caching, API key caching |
| Elasticsearch | 9.2.3 | Always — keyword search and indexing |
| Qdrant | v1.17.1 | Always — vector search |
| Ollama | — | Only if using local LLM/embedding models. Not required if you only use cloud LLM providers (OpenAI/Anthropic/Gemini/etc.) |

Versions above reflect what `docker-compose.yml`/`docker-compose.dev.yml` currently pin — verify against those files if running services independently of Compose.

## Required Environment Variables

These have no safe default; the API will not start (or will start insecurely) without them:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres connection string |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed origins — the API refuses to start if unset |
| `HARMONY_INTERNAL_TOKEN` | Shared secret the crawler subprocess uses to call internal `/api/internal/*` routes. Generate with `openssl rand -hex 32`. `docker-compose.yml` (prod) fails to start without it; `docker-compose.dev.yml` falls back to an insecure dev default if unset — do not rely on that fallback in production. |

## Optional Environment Variables

Everything below resolves through `ServiceConfigStore` with priority **ENV > DB (admin UI) > default** — if unset, either a sensible default applies or the value can be set later through the admin UI. See [CONFIGURATION.md](CONFIGURATION.md) for the full list.

| Variable | Default | Notes |
|----------|---------|-------|
| `ES_HOST` | `http://elasticsearch:9200` (Docker) | |
| `REDIS_URL` | `redis://redis:6379/0` (Docker) | |
| `HARMONY_BACKEND_URL` | `http://harmony-api:8000` (Docker) | Rarely needs override |
| `OLLAMA_HOST` | `http://localhost:11434` | Only relevant if using local models |
| `ES_INDEX_BASE_NAME`, `ES_LANGUAGES`, `ES_CONFIG_FILE` | `harmony`, `en,fr`, unset | Elasticsearch indexing config |

**LLM provider API keys are not environment variables.** They're configured after deployment through the admin UI's model registry (`/api/admin/models`), encrypted at rest. There is no `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/`GEMINI_API_KEY` env var to set — point infra at the admin UI for LLM provider setup, not `.env`.

## Authentication (Optional, Recommended for Production)

Auth is **off by default** — `AUTH_MODE=optional` runs with no OIDC configuration needed at all, useful for evaluation or fully trusted internal networks.

For any production deployment, set `AUTH_MODE=required` and configure an OIDC identity provider. Once `AUTH_MODE=required` is set, these become required alongside it:

| Variable | Purpose |
|----------|---------|
| `OIDC_ISSUER_URL` | Internal URL the API uses to validate tokens against your IdP |
| `OIDC_PUBLIC_ISSUER_URL` | Public URL the browser uses for the OIDC login redirect |
| `OIDC_CLIENT_ID` | OIDC client ID registered with your IdP |
| `OIDC_CLIENT_SECRET` | OIDC client secret |

Also set `HARMONY_SECURE_COOKIES=true` in production (HTTPS-only cookies) — the dev default (`false`) is not safe outside local development.

**Bring your own IdP in production.** `docker-compose.dev.yml` bundles a Keycloak container for local development convenience; `docker-compose.yml` (prod) does **not** include Keycloak. Point `OIDC_ISSUER_URL`/`OIDC_PUBLIC_ISSUER_URL` at your own OIDC-compliant IdP (Keycloak, Okta, Azure AD, ADFS, etc.) — don't assume Keycloak ships with a production deployment.

The bundled `sso` Compose profile (`docker compose --profile sso up`) starts an optional noVNC browser container used for *interactive SSO crawler authentication* (logging the crawler into a site that requires browser-based SSO) — this is unrelated to OIDC/Keycloak user login and is opt-in.

## Persistent Storage

These named volumes hold state that must survive container restarts/redeploys — back them up or mount them on persistent storage:

- `pg_data` — Postgres data
- `es_data` — Elasticsearch indices
- `qdrant_data` — Qdrant vector collections
- `admin_data` — admin config storage, job logs, crawler output
- `ollama_data` — pulled Ollama models (only relevant if using local models)

See [BACKUP.md](BACKUP.md) for backup/restore procedures.

## Source of Truth

This doc is derived from `docker-compose.dev.yml` (primary reference — it's the Compose file used day to day), cross-checked against `docker-compose.yml` (prod) and `.env.example`. If env vars or service versions drift from what's documented here, those three files are authoritative — verify against their current contents.
