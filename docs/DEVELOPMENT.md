# Development

## Setup

```bash
pip install -e ".[dev,test,elasticsearch]"
pre-commit install
```

## Running Services

### Dev Mode (recommended)

```bash
./dev.sh start    # Start with live reload
./dev.sh logs -f  # Stream logs
./dev.sh stop     # Stop
./dev.sh restart  # Restart
./dev.sh rebuild  # Rebuild images
./dev.sh shell [service]  # Open shell in container
```

**Dev services:**
- Admin Frontend: http://localhost:3001 (Vite dev server with HMR)
- Admin Backend API: http://localhost:8001 (FastAPI with auto-reload, docs: `/docs`)
- Elasticsearch: http://localhost:9200

Dev mode mounts source code as volumes — changes reflect immediately without rebuilding.

**Storage in dev mode** uses `.dev-data/` for easy host access:
- Configs: `.dev-data/configs/`
- Logs: `.dev-data/logs/`
- Jobs: `.dev-data/jobs/`

### Production

```bash
docker compose up -d
docker compose logs -f harmony
docker compose down
```

**Production services:**
- Admin UI: http://localhost:8080
- OpenWebUI: http://localhost:3000
- Harmony API: http://localhost:8000 (docs: `/docs`)
- Elasticsearch: http://localhost:9200
- Kibana: http://localhost:5601
- Qdrant: http://localhost:6333
- Ollama: http://localhost:11434
- Pipelines: http://localhost:9099

Production uses named volumes (`admin_data`, `es_data`, `pg_data`) for isolation. Use `docker exec` or `docker cp` to access files.

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
