# Harmony

> The opposite of Perplexity - Your own on-premise LLM-powered information retrieval system

Harmony is a fully containerized solution for creating a Perplexity-like experience with your own data. It uses hybrid search (Elasticsearch keyword + Qdrant vector) to enable LLMs to query your knowledge base without RAG, providing accurate, source-cited answers from your internal documents and data.

## Vision

A complete on-premise alternative to Perplexity that:
- **Hybrid search** - Elasticsearch keyword search + Qdrant vector search combined, not pure RAG
- **Bring Your Own LLM** - Works with local models or cloud providers (OpenAI, Anthropic, etc.)
- **Multi-source ingestion** - Crawlers and connectors for web, JIRA, Confluence, SharePoint, WordPress, Drupal, PDFs, and more
- **Fully containerized** - Deploy anywhere with Docker
- **Privacy-first** - Keep your data on-premise

## Current Status

[DONE] **Phase 1: Web Crawler & Indexer**
- Scrapy-based crawler with pluggable authentication
- Authentication: Static cookies, Basic Auth, Bearer tokens, OAuth2, Interactive SSO
- Safety mechanisms to prevent destructive actions
- HTML content expansion and document parsing (PDF, DOCX, XLSX, ODT, TXT, CSV)
- Elasticsearch indexing with metadata
- Configurable filtering and depth control
- Stateful crawling with change detection
- HTTP-based optimization (If-Modified-Since, ETag, 304 handling)
- SHA256 hash-based content comparison
- Deletion tracking with grace period
- Pause/resume support with jobdir
- Age-based re-crawling
- HTTP/HTTPS/SOCKS4/SOCKS5 proxy support

[DONE] **Phase 2: LLM Orchestration**
- Direct Elasticsearch search endpoint
- AI-powered search with tool calling and streaming
- Agentic Search multi-agent system
- K-round refinement with critic feedback
- Parallel multi-query execution
- Real-time Server-Sent Events (SSE) streaming

[DONE] **Phase 3: Chat Interface**
- OpenWebUI integration
- 3 search pipelines: Direct Search, AI Search, Agentic Search
- Docker Compose full-stack deployment
- Streaming responses with live progress indicators

[DONE] **Phase 4: Document Cache & Runtime Fetching**
- TTL-based document cache with LRU eviction
- Runtime URL and PDF fetching tools
- Universal document parser (DOCX, XLSX, ODT, TXT, CSV)
- Configurable cache settings (TTL, max size)

[DONE] **Phase 5: MCP Server Integration**
- Model Context Protocol (MCP) support
- Dynamic tool registration from MCP servers
- Stdio-based MCP client integration
- Extensible tool system with external tool servers

[DONE] **Phase 6: Hybrid Search**
- Qdrant vector database for semantic similarity search
- kv-search abstraction layer (keyword + vector + reranker pipeline)
- Keyword hits cap the vector search space (no polluted results)
- Embeddings generated via litellm (`ollama/qwen3-embedding:0.6b` recommended)
- `harmony-embed` CLI for standalone re-embedding without re-crawling
- Semantic search scaffolded (stub, not yet implemented)

[DONE] **Phase 7: Three-Stage Retrieval Pipeline**
- BM25 → vector → reranker pipeline with per-stage enable/disable flags
- `bge-reranker-v2-m3` via litellm (runs locally via Ollama, opt-in)
- All pipeline knobs runtime-mutable via `PATCH /settings/pipeline` — no restart needed
- Ollama bundled in docker-compose; pull models manually (`ollama pull bge-reranker-v2-m3`)

[TODO] **Coming Soon**
- Semantic search implementation
- Additional data connectors (JIRA, Confluence, SharePoint, WordPress, Drupal)
- Capability-based agent selection with FAISS
- Enhanced source attribution and citations

## Architecture

```
User Query → OpenWebUI → Pipelines Service → Harmony API
                                                  ↓
                                    ┌─────────────┴─────────────┐
                                    │   LLM Orchestration       │
                                    │   (3 Search Modes)        │
                                    └─────────────┬─────────────┘
                                                  ↓
                                    ┌─────────────────────────┐
                                    │   SearchService         │
                                    │   (kv-search engine)    │
                                    └──────┬──────────┬───────┘
                                           ↓          ↓
                               Elasticsearch       Qdrant
                               (keyword hits)   (vector re-rank)
                               Per-language      Filtered to
                               indices           keyword allowlist
```

### Agentic Search

```
User Query
    ↓
QueryPlannerAgent → ["variant 1", "variant 2", "variant 3"] (streaming)
    ↓
SearcherAgent (parallel) → [results_1, results_2, results_3] (streaming "Reading X")
    ↓
┌─────────── K-Round Refinement Loop ───────────┐
│  SynthesizerAgent → draft                     │
│       ↓                                        │
│  CriticAgent → critique (consensus?)          │
│       ↓                                        │
│  If consensus: exit loop                      │
│  Else: improve draft with critique (repeat)   │
└────────────────────────────────────────────────┘
    ↓
Final Answer (streaming tokens) + Sources + Citations
```

## Quick Start

```bash
# Create .env file with your API keys
cp .env.example .env

# Start all services
docker compose up -d
```

**Services:**
- OpenWebUI: http://localhost:3000
- Harmony API: http://localhost:8000
- Elasticsearch: http://localhost:9200
- Kibana: http://localhost:5601
- Qdrant: http://localhost:6333
- Pipelines: http://localhost:9099

## Installation

```bash
pip install -e .

# For Elasticsearch indexing
pip install -e ".[elasticsearch]"

# For browser automation (JS-heavy sites and interactive SSO)
pip install -e ".[browser]"
playwright install chromium
```

## Usage

### Crawling

```bash
harmony-crawl \
  --crawler.start_urls+ https://example.com \
  --crawler.output crawled_data \
  --crawler.max_depth 100
```

See [docs/CRAWLER.md](docs/CRAWLER.md) for full crawler docs including safety, stateful crawling, authentication, and proxy support.

### Indexing

```bash
harmony-index \
  --data-dir output \
  --es-config configs/es_config.yaml
```

See [docs/INDEXING.md](docs/INDEXING.md) for detailed indexing instructions.

### API

**Direct Search:**
```bash
curl "http://localhost:8000/search?q=your+query"
```

**AI Search (streaming):**
```bash
curl -N -X POST http://localhost:8000/ai-search \
  -H "Content-Type: application/json" \
  -d '{"query": "What is CERN?"}'
```

**Agentic Search (multi-agent streaming):**
```bash
curl -N -X POST http://localhost:8000/agentic-search \
  -H "Content-Type: application/json" \
  -d '{"query": "What is CERN?", "max_refinement_rounds": 3}'
```

Use `-N` with curl to disable buffering for streaming events.

**SSE event types:** `query_variant`, `reading_page`, `refinement_round`, `answer_chunk`, `tool_call`, `done`, `error`

### OpenWebUI

1. Access http://localhost:3000
2. Select a pipeline: **Direct Search**, **AI Search**, or **Agentic Search**
3. Ask questions about your indexed data

## Documentation

- [docs/CRAWLER.md](docs/CRAWLER.md) — crawling, safety, stateful crawling, authentication
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md) — all environment variables and config files
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — setup, testing, running services
- [docs/INDEXING.md](docs/INDEXING.md) — Elasticsearch indexing
- [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) — authentication methods
- [docs/ES_MIGRATION.md](docs/ES_MIGRATION.md) — migrating from single-index setup
- [docs/CUSTOM_AUTH_PROVIDER.md](docs/CUSTOM_AUTH_PROVIDER.md) — writing custom auth providers

## Technology Stack

- **FastAPI** — async web framework
- **LiteLLM** — universal LLM API (100+ providers)
- **Elasticsearch 9.x** — search and indexing
- **Qdrant** — vector search
- **Scrapy** — web crawling
- **OpenWebUI** — chat interface
- **Docker Compose** — full-stack orchestration
- **Python 3.13**

## Roadmap

### Next Steps

#### Code Quality
- [ ] Add docstrings to all modules
- [ ] Increase test coverage to >90%
- [ ] Add integration tests for end-to-end workflows

#### Data Connectors
- [ ] JIRA, Confluence, SharePoint, WordPress, Drupal connectors
- [ ] Generic REST API connector

#### Advanced Features
- [ ] Semantic search implementation
- [ ] FAISS-based capability matching for agent selection
- [ ] Query history and analytics
- [ ] Custom agent plugins system

#### Enterprise
- [ ] User authentication and authorization
- [ ] Multi-tenant support
- [ ] Audit logging, rate limiting, admin dashboard

## License

Other/Proprietary License - See LICENSE file for details.

## Acknowledgments

- Inspired by the [Federation of Agents](https://arxiv.org/abs/2509.20175) paper
- Built with [OpenWebUI](https://github.com/open-webui/open-webui)
- Search powered by [Elasticsearch](https://www.elastic.co/)
- LLM integration via [LiteLLM](https://github.com/BerriAI/litellm)
