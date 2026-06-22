# AGENTS.md

This file provides guidance to AI coding assistants like Claude Code, Gemini CLI, Copilot CLI or Cursor when working with code in this repository.

## Project Overview

Harmony is a fully containerized, on-premise alternative to Perplexity for LLM-powered information retrieval. It uses hybrid search (Elasticsearch keyword + Qdrant vector via kv-search) rather than pure RAG, enabling LLMs to query structured and unstructured data with precise retrieval.

For architecture, data models, and service patterns, see `.claude/rules/`:

- [architecture.md](.claude/rules/architecture.md) — high-level flow, provider plugin pattern, auth, streaming, DB layer
- [data-models.md](.claude/rules/data-models.md) — where models live and how to find them
- [patterns.md](.claude/rules/patterns.md) — service lifecycle, config resolution, adding agents/tools/routes
- [config.md](.claude/rules/config.md) — env vars and YAML config reference

These rules files describe durable decisions, not a file census — for current file layout use `codebase-memory-mcp`'s `get_architecture`/`search_graph`/`search_code`.

## Development Commands

### Setup

```bash
pip install -e ".[dev,test,elasticsearch]"
pre-commit install
```

### Testing

```bash
# Run default tests (unit tests only, no external dependencies)
pytest tests/

# Run specific test categories
pytest tests/ -m "elasticsearch"  # Requires ES running
pytest tests/ -m "llm"            # Requires LLM API keys
pytest tests/ -m "integration"    # Requires all services

# Run all tests including external dependencies
pytest tests/ --override-ini="addopts="

# Run with coverage
pytest --cov=harmony tests/
```

**Default:** only unit tests run unless explicitly requested.

### Code Quality

```bash
pre-commit run --all-files
ruff check --fix --unsafe-fixes --preview .
ruff format .
mypy harmony/
```

### Running Services (development)

```bash
./dev.sh start     # dev environment with live reload
./dev.sh logs [service] [-f]
./dev.sh stop
./dev.sh restart
./dev.sh rebuild
./dev.sh shell [service]
```

- Admin Frontend: <http://localhost:8080> (Vite dev server with HMR, proxies API calls to port 8000)
- API: <http://localhost:8000> (single FastAPI server, docs: /docs) — serves both search and `/api/admin/*` routes
- Elasticsearch: <http://localhost:9200>
- Keycloak: <http://localhost:9092> (OIDC provider, dev realm auto-imported from `keycloak/harmony-realm.json`)

Development mode mounts source code as volumes for instant hot reload.

### Running Services (production)

```bash
docker compose up -d
docker compose logs -f harmony-api
docker compose down
```

Services: Admin UI (8080), Harmony API (8000, docs at /docs), Elasticsearch (9200), Kibana (5601), Qdrant (6333), Ollama (11434, models: qwen3-embedding:0.6b, bge-reranker-v2-m3), Postgres, Redis.

### Crawling and Indexing

`harmony-crawl` and `harmony-index` are CLI entry points for the web crawler provider (`harmony-crawl --help` / `harmony-index --help`) — used occasionally for manual/ad-hoc crawls, not part of the main day-to-day workflow. See [architecture.md](.claude/rules/architecture.md#provider-plugin-pattern) for the provider pattern. To re-embed existing documents after changing the embedding model without re-crawling: `harmony-embed --embedder.es-config configs/es_config.yaml`.

## Code Style Guidelines

### Type Hints

- Always use `from __future__ import annotations` at top of file
- All functions must have type hints
- Use `|` for union types: `str | None`
- Use class literals as types: `list[str]`, `dict[str, int]`

### Imports

- Third-party: `import xxx.yyy` and use as `xxx.yyy.Zzz`
- Intra-package: `from xxx.yyy import Zzz`
- Never use wildcard imports
- All imports at top of file

### Testing

- Prefer functional tests: `def test_something()` over class-based
- Use pytest markers for external dependencies
- Default: only unit tests run

### Git Workflow

- Use conventional commits
- Every commit message must be prefixed with the Jira ticket key (e.g. `HRM-42 feat(auth): ...`). If the ticket key is not known, ask the user before committing — never commit without it.
- Never use `git add -A`
- Keep commit messages simple
- Ensure tests pass before committing
- Never commit with `--no-verify` unless explicitly requested

### General

- No unnecessary print statements
- No comments when code is self-evident
- Run `ruff check --fix --unsafe-fixes --preview` before commit
- Ensure pre-commit passes
- Prefer functional over class-based tests

## CI/CD

- GitHub Actions workflow in `.github/workflows/test.yml`
- Runs unit tests, Elasticsearch tests, and linting
- Uses `docker-compose.test.yml` for CI environment

Make sure to read
@.claude/CLAUDE.local.md
