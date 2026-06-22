# Development

## Setup

```bash
pip install -e ".[dev,test]"
pre-commit install
```

Elasticsearch support is a core dependency now, not an optional extra.

## Running Services

### Dev Mode (recommended)

```bash
./dev.sh start         # Start dev environment with live reload
./dev.sh logs [service] [-f]
./dev.sh stop
./dev.sh restart
./dev.sh rebuild
./dev.sh shell [service]  # Open shell in container
```

**Dev services:**
- Admin Frontend: <http://localhost:8080> (Vite dev server with HMR, proxies API calls to port 8000)
- API: <http://localhost:8000> (single FastAPI server, docs: `/docs`) — serves both search and `/api/admin/*` routes
- Elasticsearch: <http://localhost:9200>
- Keycloak: <http://localhost:9092> (OIDC provider, dev realm auto-imported from `keycloak/harmony-realm.json`)

Dev mode mounts source code as volumes — changes reflect immediately without rebuilding.

**Storage in dev mode** uses `.dev-data/` for easy host access (configs, logs, crawl output).

### Production

```bash
docker compose up -d
docker compose logs -f harmony-api
docker compose down
```

**Production services:**
- Harmony (chat + admin UI): <http://localhost:8080>
- Harmony API: <http://localhost:8000> (docs: `/docs`)
- Elasticsearch: <http://localhost:9200>
- Kibana: <http://localhost:5601>
- Qdrant: <http://localhost:6333>
- Ollama: <http://localhost:11434>

Production uses named volumes (`admin_data`, `es_data`, `pg_data`, `qdrant_data`, `ollama_data`) for persistence. Use `docker exec` or `docker cp` to access files. See [DEPLOYMENT.md](DEPLOYMENT.md) for required configuration.

### API Server (local, no Docker)

```bash
harmony-api
# or
uvicorn harmony.api.main:app --reload --host 0.0.0.0 --port 8000
```

## Testing

By default, only unit tests run (no external dependencies):

```bash
pytest tests/
```

**With external dependencies:**
```bash
# Elasticsearch tests (requires ES running)
pytest tests/ -m "elasticsearch or (not llm and not integration)"

# LLM tests (requires API keys)
pytest tests/ -m "llm or (not elasticsearch and not integration)"

# Integration tests (requires all services)
pytest tests/ -m "integration"

# All tests
pytest tests/ --override-ini="addopts="
```

**Other useful commands:**
```bash
pytest tests/test_conversation.py -v   # Specific file
pytest --cov=harmony tests/            # With coverage
```

**Test markers:**
- `@pytest.mark.llm` — requires LLM API calls
- `@pytest.mark.elasticsearch` — requires ES connection
- `@pytest.mark.integration` — requires all services running

## Code Quality

```bash
pre-commit run --all-files
```

Individual tools (prefer pre-commit):
```bash
ruff check --fix --unsafe-fixes --preview .
ruff format .
mypy harmony/
```
