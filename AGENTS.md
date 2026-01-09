# AGENTS.md

This file provides guidance to AI coding assistants like Claude Code, Gemini CLI, Copilot CLI or Cursor when working with code in this repository.

## Project Overview

Harmony is a fully containerized, on-premise alternative to Perplexity for LLM-powered information retrieval. Unlike RAG-based systems, Harmony uses Elasticsearch for precise search, enabling LLMs to query structured and unstructured data.

**Current Status:** Fully functional with web crawler, Elasticsearch indexing, multi-agent LLM orchestration, and OpenWebUI integration.

## Development Commands

### Setup
```bash
# Install in development mode
pip install -e ".[dev,test,elasticsearch]"

# Install pre-commit hooks
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

# Run specific test file
pytest tests/test_conversation.py -v

# Run with coverage
pytest --cov=harmony tests/
```

**Test markers:**
- `@pytest.mark.llm` - Tests requiring real LLM API calls
- `@pytest.mark.elasticsearch` - Tests requiring ES connection
- `@pytest.mark.integration` - Tests requiring external services

**Default:** Only unit tests run unless explicitly requested.

### Code Quality
```bash
# Run all pre-commit checks
pre-commit run --all-files

# Linting (matches pre-commit config)
ruff check --fix --unsafe-fixes --preview .

# Format code
ruff format .

# Type checking
mypy harmony/
```

### Running Services

**Full stack:**
```bash
# Start all services (Harmony API, Elasticsearch, Kibana, OpenWebUI, Pipelines)
docker compose up -d

# View logs
docker compose logs -f harmony

# Stop services
docker compose down
```

**Services:**
- OpenWebUI: http://localhost:3000
- Harmony API: http://localhost:8000 (docs: /docs)
- Elasticsearch: http://localhost:9200
- Kibana: http://localhost:5601
- Pipelines: http://localhost:9099

**API server (development):**
```bash
# Run with auto-reload
harmony-api

# Or via uvicorn directly
uvicorn harmony.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Crawling and Indexing

**Basic crawl:**
```bash
harmony-crawl \
  --crawler.start_urls+ https://example.com \
  --crawler.output crawled_data \
  --crawler.max_depth 100
```

**Crawl with config file:**
```bash
harmony-crawl --config harmony_config.yaml --crawler.output output/
```

**Stateful crawl (with change detection):**
```bash
harmony-crawl \
  --config harmony_config.yaml \
  --crawler.es_state_host http://localhost:9200 \
  --crawler.jobdir .crawl-state
```

**Index crawled data:**
```bash
# Using config file (recommended)
harmony-index \
  --data-dir output \
  --es-config es_config.yaml

# Or with CLI arguments
harmony-index \
  --data-dir output \
  --es-host http://localhost:9200 \
  --index-base-name harmony \
  --languages en,fr,de,es
```

**Safety modes:**
```bash
# Test without making requests
harmony-crawl --config config.yaml --crawler.dry_run

# Extra strict safety checks
harmony-crawl --config config.yaml --crawler.safe_mode

# Interactive safety (build allow/deny lists)
harmony-crawl --config config.yaml --crawler.interactive_safety true
```

## Architecture

### High-Level Flow

```
User Query → OpenWebUI → Pipelines → Harmony API
                                           ↓
                         ┌─────────────────┴─────────────────┐
                         │   LLM Orchestration               │
                         │   (Direct/AI/Agentic Search)      │
                         └─────────────────┬─────────────────┘
                                           ↓
                         ┌─────────────────────────────────┐
                         │   Elasticsearch                 │
                         │   Per-Language Indices          │
                         │   (harmony-en, harmony-fr, ...) │
                         └─────────────────────────────────┘
```

### Crawler Architecture (`harmony/crawler/`)

**Entry point:** `cli.py` uses jsonargparse for configuration

**Key components:**
- `spiders/harmony.py` - Main Scrapy spider
- `middlewares.py` - SafetyMiddleware, DomainRouterMiddleware, DeltaFetchMiddleware
- `safety.py` - SafetyConfig with URL pattern blocking
- `safety_lists.py` - Persistent allow/deny patterns (`.harmony-safety-lists.json`)
- `pipelines.py` - HTMLExpanderPipeline, FileStoragePipeline
- `state.py` - CrawlStateManager for ES-backed state tracking
- `items.py` - PageItem, DocumentItem
- `config.py` - YAML configuration loader

**Safety architecture (defense-in-depth):**
1. LinkExtractor deny patterns - Early filtering at link extraction
2. SafetyMiddleware - Runtime request filtering
3. HTTP method restriction - Only GET/HEAD by default
4. Interactive mode - Build allow/deny lists on-the-fly
5. Persistent patterns - Save learned patterns to `.harmony-safety-lists.json`

**State management:**
- Separate ES index (`harmony-crawl-state`) tracks metadata
- HTTP-based change detection (If-Modified-Since, ETag, 304)
- SHA256 hash comparison for content changes
- Deletion tracking with grace period
- Age-based re-crawling support

**Crawl flow:**
1. Load config from YAML or CLI
2. SafetyMiddleware checks requests
3. DeltaFetchMiddleware checks for changes (if state enabled)
4. DomainRouterMiddleware routes by domain
5. Extract links with deny patterns
6. HTMLExpanderPipeline expands collapsed content
7. FileStoragePipeline saves to disk + metadata.jsonl

### API Architecture (`harmony/api/`)

**Entry point:** `main.py` - FastAPI app with lifespan context manager
- Startup: Initialize ES, document cache, tool registry, MCP servers
- Shutdown: Close connections, cleanup resources

**Routes (`routes/`):**
- `search.py` - Direct ES search (`GET /search?q=query`)
- `chat.py` - AI-powered search with tool calling (`POST /ai-search`)
- `agentic_search.py` - Multi-agent search (`POST /agentic-search`)

**Services (`services/`):**
- `elasticsearch.py` - ESService for per-language index management
- `llm.py` - LLMService wrapping LiteLLM (supports 100+ providers)
- `conversation.py` - ConversationService for multi-turn chat
- `document_cache.py` - LRU cache with TTL for fetched documents
- `prompts.py` - Jinja2-based prompt template management
- `language_detection.py` - Language detection for multilingual search

**Agents (`agents/`):**
Multi-agent system implementing Federation of Agents pattern:
- `base.py` - BaseAgent abstract class
- `query_planner.py` - QueryPlannerAgent (generates search variants)
- `searcher.py` - SearcherAgent (executes ES queries)
- `critic.py` - CriticAgent (validates answers, provides feedback)
- `synthesizer.py` - SynthesizerAgent (generates/refines answers)
- `orchestrator.py` - AgenticOrchestrator (coordinates workflow)

**Agentic search flow:**
```
1. QueryPlannerAgent → ["variant 1", "variant 2", "variant 3"]  (streamed)
2. SearcherAgent (parallel) → [results_1, results_2, results_3]  (streamed)
3. K-Round Refinement Loop (k=3):
   - SynthesizerAgent → draft answer
   - CriticAgent → critique (checks consensus)
   - If consensus: exit loop
   - Else: improve draft with critique
4. Final answer (streamed) + sources + citations
```

**Tools (`tools/`):**
- `registry.py` - ToolRegistry for dynamic tool management
- `search.py` - search_documents_tool, get_document_details_tool
- `documents.py` - fetch_url_tool, fetch_pdf_tool, fetch_document_tool
- `mcp.py` - MCPServerLoader for Model Context Protocol integration

**Streaming:**
All search endpoints return Server-Sent Events (SSE):
- `query_variant` - Each search variant as generated
- `reading_page` - Per unique page during search
- `refinement_round` - Round start/complete with consensus status
- `answer_chunk` - Answer tokens in real-time
- `tool_call` - Tool execution events
- `done` - Final metadata (sources, rounds, variants)
- `error` - Error messages

### Indexer Architecture (`harmony/indexer/`)

**Entry point:** `cli.py` - Bulk indexing with language detection

**Two source modes:**
- `--source disk` (default): Reads from metadata.jsonl files on disk
- `--source elasticsearch`: Queries ES state index (harmony-crawl-state)

Both modes:
- Read file content from disk (--data-dir) for text extraction
- Support all document parsers (PDF, DOCX, XLSX, etc.)
- Work with deletion sync (--sync-deletions)
- Use same processing pipeline after initial loading

**Per-language indices:**
- Index naming: `{base_name}-{language_code}` (e.g., `harmony-en`)
- Language-specific analyzers (English → `english`, French → `french`)
- Automatic language detection during crawling
- Multi-language search across all configured indices
- 12 supported languages: en, fr, de, es, it, pt, nl, ru, ar, zh, ja, ko

**Indexing flow (disk source):**
1. Recursively find all `metadata.jsonl` files
2. For each entry, resolve HTML file path
3. Extract title and text content (strip scripts/styles)
4. Detect language
5. Create ES document with metadata + content
6. Bulk index to language-specific index

**Indexing flow (elasticsearch source):**
1. Query all documents from ES state index
2. Transform state records to entry format
3. For each entry, resolve HTML file path
4. Extract title and text content (strip scripts/styles)
5. Detect language (if not in state)
6. Create ES document with metadata + content
7. Bulk index to language-specific index

### OpenWebUI Pipelines (`openwebui_pipelines/`)

**CRITICAL: Manifold pipelines must use synchronous generators**

OpenWebUI pipelines do NOT support `async def pipe()`:
- Must use synchronous `def pipe()` (not `async def`)
- Return type: `Generator[str, None, None]` (not `AsyncGenerator`)
- Use `httpx.Client()` (not `AsyncClient()`)
- Use `for line in response.iter_lines()` (not `async for`)

**Reason:** Async generators get exhausted during OpenWebUI's inspection.

**Pipelines:**
- `harmony_direct_search.py` - Direct ES search
- `harmony_search_model.py` - AI Search with tool calling
- `harmony_agentic_search.py` - Agentic multi-agent search

Each pipeline:
1. Proxies requests to Harmony API
2. Parses SSE responses
3. Yields plain text chunks to OpenWebUI
4. Type: `manifold` (provides multiple models)

## Configuration

### Environment Variables

**LLM provider (choose one):**
```bash
# Gemini
GEMINI_API_KEY=your_key
LLM_MODEL=gemini/gemini-3-flash-preview

# OpenAI
OPENAI_API_KEY=your_key
LLM_MODEL=gpt-4

# Anthropic
ANTHROPIC_API_KEY=your_key
LLM_MODEL=claude-3-5-sonnet-20241022

# Ollama (local, no key required)
LLM_MODEL=ollama_chat/llama3
OLLAMA_HOST=http://localhost:11434
```

See https://docs.litellm.ai/docs/providers for all supported models.

**Elasticsearch:**
```bash
# Use config file (recommended)
ES_CONFIG_FILE=es_config.yaml

# Or individual settings
ES_HOST=http://localhost:9200
ES_INDEX_BASE_NAME=harmony
ES_LANGUAGES=en,fr,de,es
```

**Document cache:**
```bash
DOCUMENT_CACHE_ENABLED=true
DOCUMENT_CACHE_TTL=3600        # 1 hour
DOCUMENT_CACHE_MAX_SIZE=1000
```

**Agentic search:**
```bash
AGENTIC_MAX_REFINEMENT_ROUNDS=3
AGENTIC_MAX_QUERY_VARIANTS=4
AGENTIC_SEARCH_TOP_K=10
AGENTIC_MAX_SOURCES_RETURNED=10
```

**MCP servers:**
```bash
MCP_SERVERS='[
  {
    "name": "filesystem",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"],
    "env": {}
  }
]'
```

### YAML Configuration

**Crawler config (`harmony_config.yaml`):**
```yaml
start_urls:
  - "https://docs.example.com"

# Proxy (optional)
proxy:
  url: http://proxy.example.com:8080  # Scheme determines type (http/https/socks4/socks5)
  username: user  # optional
  password: pass  # optional

# Domain routing
domain_routing:
  exact:
    "docs.example.com": docs
  patterns:
    - pattern: ".*-docs\\..*"
      spider: docs
  default: generic

# Spider settings
spider_settings:
  docs:
    skip_versions: true
    version_allowlist: [stable, latest, current]

# Safety lists
crawler:
  safety_allow_list:
    - "example\\.com/admin/view.*"
  safety_deny_list:
    - "/private/.*"
```

**Elasticsearch config (`es_config.yaml`):**
```yaml
host: http://localhost:9200
index_base_name: harmony
languages:
  - en
  - fr
  - de
  - es

# Immutable settings (index creation only)
immutable:
  number_of_shards: 1
  number_of_replicas: 0

# Mutable settings (runtime tunable)
mutable:
  title_boost: 2.0
  content_boost: 1.0
```

## Development Patterns

### Adding a New Agent

1. Create agent in `harmony/api/agents/`:
```python
from __future__ import annotations

from harmony.api.agents.base import BaseAgent

class MyAgent(BaseAgent):
    async def execute(self, input_data: dict) -> dict:
        # Agent logic
        return result
```

2. Register in orchestrator (`harmony/api/agents/orchestrator.py`)

### Adding a New Tool

1. Create tool in `harmony/api/tools/`:
```python
from __future__ import annotations

from harmony.api.tools.registry import tool

@tool
async def my_tool(param: str) -> str:
    """Tool description for LLM."""
    return result
```

2. Register in `harmony/api/main.py` lifespan:
```python
tool_registry.register(my_tool)
```

### Adding a New Route

1. Create route in `harmony/api/routes/`:
```python
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

@router.post("/my-endpoint")
async def my_endpoint(data: dict) -> dict:
    return result
```

2. Include in `harmony/api/main.py`:
```python
from harmony.api.routes import my_route
app.include_router(my_route.router)
```

### Streaming SSE Responses

All streaming endpoints follow this pattern:
```python
from sse_starlette.sse import EventSourceResponse

async def event_generator():
    yield {"event": "query_variant", "data": json.dumps({"variant": query})}
    yield {"event": "answer_chunk", "data": json.dumps({"chunk": token})}
    yield {"event": "done", "data": json.dumps({"sources": [...]})}

@router.post("/my-search")
async def my_search(request: SearchRequest):
    return EventSourceResponse(event_generator())
```

### Adding Prompt Templates

1. Create Jinja2 template in `harmony/prompts/`:
```
harmony/prompts/
  system/
    my_agent.jinja2
  user/
    my_query.jinja2
```

2. Load in agent:
```python
from harmony.api.services.prompts import prompt_manager

system_prompt = await prompt_manager.render(
    "system/my_agent.jinja2",
    context={"key": "value"}
)
```

### Writing Tests

Use pytest with async support:
```python
from __future__ import annotations

import pytest

from harmony.api.services.llm import llm_service

@pytest.mark.llm  # Mark for LLM API tests
async def test_my_feature() -> None:
    result = await llm_service.completion(messages=[...])
    assert result

@pytest.mark.elasticsearch  # Mark for ES tests
async def test_search() -> None:
    from harmony.api.services.elasticsearch import es_service

    results = await es_service.search(query="test")
    assert results
```

## Testing

**Running tests:**
```bash
# Run default tests (unit tests only, no external dependencies)
pytest tests/

# Run with Elasticsearch tests (requires ES running)
./scripts/test-with-es.sh

# Or manually
docker compose -f docker-compose.test.yml up -d
pytest tests/ -m "elasticsearch"
docker compose -f docker-compose.test.yml down -v
```

**Test markers:**
- `@pytest.mark.elasticsearch` - Tests requiring ES connection
- `@pytest.mark.llm` - Tests requiring LLM API calls
- `@pytest.mark.integration` - Tests requiring external services

**CI/CD:**
- GitHub Actions workflow in `.github/workflows/test.yml`
- Runs unit tests, Elasticsearch tests, and linting
- Uses `docker-compose.test.yml` for CI environment

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

## Important Notes

### Crawler Safety
- Never disable safety mechanisms without review
- Always test new targets with `--crawler.dry_run` first
- Review blocked URLs in logs
- Use `--crawler.safe_mode` for unknown sites
- Respect robots.txt (default)
- Safety architecture uses defense-in-depth

### OpenWebUI Pipelines
- Must use synchronous generators (`def pipe()`)
- Use `httpx.Client()`, not `AsyncClient()`
- Parse SSE and yield plain text (not JSON)
- Type: `manifold` for multiple models
- See [OpenWebUI docs](https://docs.openwebui.com/features/plugin/functions/pipe/)

### LLM Integration
- Uses LiteLLM for universal LLM access
- Supports 100+ providers via model ID
- See https://docs.litellm.ai/docs/providers

### Elasticsearch
- Per-language indices for optimal search
- Language-specific analyzers
- Automatic language detection
- Multi-language search across indices
