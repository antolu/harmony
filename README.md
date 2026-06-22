# Harmony

> The opposite of Perplexity — your own on-premise LLM-powered information retrieval system

Harmony is a fully containerized, on-premise alternative to Perplexity. It crawls and indexes your internal and external data with hybrid search (Elasticsearch BM25 keyword + Qdrant vector), then exposes it through a multi-agent, hybrid-search-based RAG pipeline — giving you accurate, source-cited answers from your own documents without sending your data to a third party.

## Key Features

- **Hybrid search retrieval** — Elasticsearch (BM25 keyword) + Qdrant (vector) combined; keyword hits cap the vector search space, then an optional reranker (`bge-reranker-v2-m3`) re-scores the merged results
- **Advanced multi-agent RAG** — agentic search runs a QueryPlanner → parallel Searchers → Synthesizer/Critic refinement loop over the retrieval pipeline, streamed live via SSE, with inline citations
- **Native chat UI** — multi-turn conversations, streaming markdown, inline citations, thumbs up/down feedback, per-group model selection, dark/light mode; this is the homepage, no separate chat tool required
- **Admin dashboard** — job monitoring with live log streaming, data source CRUD + YAML import/export + cron scheduling, document/URL browser with ES+Qdrant deletion and blacklisting, LLM/model provider management, token usage dashboard, audit log, pipeline settings, encrypted API key storage, webhook notifications, backup/restore
- **Bring your own LLM** — any provider supported by LiteLLM (OpenAI, Anthropic, Gemini, Ollama, 100+ others), configured at runtime through the admin UI, not env vars or redeploys
- **Pluggable data sources** — "data source" is the top-level ingestion abstraction; built-in providers are a web crawler (with safety middleware, auth providers, delta-fetch) and a filesystem ingester, with third-party providers registerable via Python entry points
- **Enterprise auth** — JWT-based auth with OIDC/SSO (Keycloak by default, any OIDC-compliant IdP), API keys, role-based authorization, and per-user ACL filtering applied at query time in Elasticsearch
- **Multi-language search** — per-index support across 12 languages
- **Fully containerized** — Docker Compose for a single server today; Kubernetes is on the roadmap (see [Future](#future))
- **Privacy-first** — no external calls except to the LLM/embedding providers you explicitly configure

## Architecture

```
User Query → Harmony API
                  ↓
            ┌─────┴─────────────────────┐
            │   LLM Orchestration       │
            │   (Direct / AI / Agentic) │
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

A single FastAPI app serves both the search/chat API and all admin routes (`/api/admin/*`) — there's no separate admin server. The admin frontend is a separate Vite/React app that proxies API calls in dev.

### Agentic Search

```
1. QueryPlannerAgent → query variants (streamed)
2. SearcherAgent (parallel) → search results per variant (streamed)
3. K-Round Refinement Loop:
   - SynthesizerAgent → draft answer
   - CriticAgent → critique (checks consensus)
   - exit loop on consensus, else improve draft with critique
4. Final answer (streamed) + sources + citations
```

Each agent has one responsibility; the orchestrator coordinates; the searcher never touches Elasticsearch/Qdrant directly, only through `SearchService`.

## Quick Start

```bash
cp .env.example .env
# edit .env — set HARMONY_INTERNAL_TOKEN and CORS_ALLOWED_ORIGINS at minimum

docker compose up -d
```

**Services:**

- Harmony (chat + admin UI): <http://localhost:8080>
- Harmony API (docs at `/docs`): <http://localhost:8000>
- Elasticsearch: <http://localhost:9200>
- Kibana: <http://localhost:5601>
- Qdrant: <http://localhost:6333>
- Ollama: <http://localhost:11434>

LLM providers and models are configured after startup through the admin UI's setup wizard (or `/api/admin/models`), not through environment variables — see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for required vs. optional configuration.

## Installation (development)

```bash
pip install -e ".[dev,test]"
pre-commit install
```

Elasticsearch support is a core dependency, not an optional extra. For browser-based crawling (JS-heavy sites, interactive SSO):

```bash
pip install -e ".[browser]"
playwright install chromium
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the full dev workflow (`./dev.sh`).

## Usage

### Chat

Open <http://localhost:8080> and start a conversation. Pick a search mode and model from the chat UI.

### API

**Direct search:**

```bash
curl "http://localhost:8000/api/search?q=your+query"
```

**AI search (streaming):**

```bash
curl -N -X POST http://localhost:8000/api/ai-search \
  -H "Content-Type: application/json" \
  -d '{"query": "What is CERN?"}'
```

**Agentic search (multi-agent, streaming):**

```bash
curl -N -X POST http://localhost:8000/api/agentic-search \
  -H "Content-Type: application/json" \
  -d '{"query": "What is CERN?", "max_refinement_rounds": 3}'
```

Use `-N` with curl to disable buffering for streaming endpoints.

**SSE event types:** `query_variant`, `reading_page`, `refinement_round`, `answer_chunk`, `tool_call`, `done`, `error`

### Crawling and indexing

```bash
harmony-crawl --crawler.start_urls+ https://example.com --crawler.output crawled_data
harmony-index --data_dir crawled_data --es_config configs/es_config.yaml
```

Typically run through the admin UI's data source scheduler rather than manually — see [docs/CRAWLER.md](docs/CRAWLER.md) and [docs/INDEXING.md](docs/INDEXING.md).

## Documentation

- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — required/optional config, services, secrets for deploying outside dev
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md) — environment variables and config files
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — local dev setup, testing, running services
- [docs/PROVIDERS.md](docs/PROVIDERS.md) — data source provider model, writing custom providers
- [docs/FRONTEND.md](docs/FRONTEND.md) — frontend architecture (chat + admin app split)
- [docs/CRAWLER.md](docs/CRAWLER.md) — crawling, safety, stateful crawling, authentication
- [docs/INDEXING.md](docs/INDEXING.md) — Elasticsearch indexing
- [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) — authentication methods
- [docs/CUSTOM_AUTH_PROVIDER.md](docs/CUSTOM_AUTH_PROVIDER.md) — writing custom crawler auth providers
- [docs/ES_MIGRATION.md](docs/ES_MIGRATION.md) — migrating from a single-index setup
- [docs/BACKUP.md](docs/BACKUP.md) — backup and restore

## Technology Stack

- **FastAPI** — async web framework
- **LiteLLM** — universal LLM API (100+ providers)
- **Elasticsearch 9.x** — keyword search and indexing
- **Qdrant** — vector search
- **PostgreSQL** — jobs, schedules, audit log, model registry, users, conversations
- **Redis** — pub/sub and session caching
- **Scrapy** — web crawling
- **React / Vite** — admin and chat frontend
- **Keycloak** (default) — OIDC identity provider; any OIDC-compliant IdP works
- **Docker Compose** — deployment orchestration
- **Python 3.13**

## Future

Items not yet built, in rough priority order:

- **Kubernetes deployment** — stateless API, job executor abstraction (subprocess/K8s env-var switch), vLLM serving, K8s manifests (base + dev/prod overlays, RBAC, HPAs, PVCs); Docker Compose remains the supported path until this lands
- **Additional data connectors** — JIRA, Confluence, SharePoint, WordPress, Drupal, generic REST API
- **SAML 2.0** as a second auth provider alongside OIDC
- **Group-based model access policy** (currently role-based only)
- **Responsive/accessible UI redesign** across the admin frontend (not yet WCAG 2.1 AA audited)
- **Rate limiting / throttling** per-user and per-endpoint
- **Structured log forwarding** to Kibana/Grafana
- **Token quota enforcement** (usage tracking and alerting already shipped; hard enforcement is v2)

## License

Other/Proprietary License — see LICENSE file for details.

## Acknowledgments

- Inspired by the [Federation of Agents](https://arxiv.org/abs/2509.20175) paper
- Search powered by [Elasticsearch](https://www.elastic.co/) and [Qdrant](https://qdrant.tech/)
- LLM integration via [LiteLLM](https://github.com/BerriAI/litellm)
