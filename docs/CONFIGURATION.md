# Configuration

## LLM Providers and Models

LLM provider API keys are **not** environment variables. They're managed at runtime through the admin UI's model registry (`/api/admin/models`), encrypted at rest via `SecretValueService`. Add a provider, paste its key, and select a model — no restart needed. Any provider supported by [LiteLLM](https://docs.litellm.ai/docs/providers) works (OpenAI, Anthropic, Gemini, Ollama, and 100+ others).

`OLLAMA_HOST` is the one LLM-related setting still resolved via `ServiceConfigStore` (ENV > DB > default) — it defaults to the bundled `ollama` container in Docker Compose; override it to point at an external Ollama instance.

## Environment Variables

Most runtime-tunable settings (Elasticsearch/Qdrant/Redis hosts, OIDC, auth mode, document cache, agentic search tuning) are **not** plain `Settings` fields — they resolve through `ServiceConfigStore` with priority ENV > DB (admin UI) > default. See [`harmony/api/services/admin/_service_config.py`](../harmony/api/services/admin/_service_config.py) for the full field list, or `GET /api/admin/configs` for the live resolved values. The sections below cover the env vars most relevant to a fresh deployment — see [DEPLOYMENT.md](DEPLOYMENT.md) for the required-vs-optional breakdown.

### API Server

```bash
API_HOST=0.0.0.0
API_PORT=8000
```

### Elasticsearch

```bash
# Use a config file (recommended)
ES_CONFIG_FILE=configs/es_config.yaml

# Or set individually
ES_HOST=http://localhost:9200
ES_INDEX_BASE_NAME=harmony
ES_LANGUAGES=en,fr,de,es
```

### Qdrant / Embeddings

```bash
QDRANT_HOST=http://localhost:6333
PIPELINE_EMBEDDING_BATCH_SIZE=64
```

The embedding model and Qdrant collection name/vector size are **not** env vars — they're set via the admin setup wizard (`harmony/api/routes/admin/setup.py`) and stored through `ModelSettingsStore`/`ModelRegistryService`, since vector size must match whatever embedding model is selected (e.g. `ollama/qwen3-embedding:0.6b` → 512 dims). `EMBEDDING_MODEL` works as an env-var override of the stored value if set, but the normal path is the setup wizard.

### Document Cache

```bash
DOCUMENT_CACHE_ENABLED=true
DOCUMENT_CACHE_TTL=3600         # seconds
DOCUMENT_CACHE_MAX_SIZE=1000
```

### Agentic Search

```bash
PIPELINE_AGENTIC_MAX_REFINEMENT_ROUNDS=3
PIPELINE_AGENTIC_MAX_QUERY_VARIANTS=4
PIPELINE_AGENTIC_SEARCH_TOP_K=10
PIPELINE_AGENTIC_MAX_SOURCES_RETURNED=10
```

## Elasticsearch Config (`configs/es_config.yaml`)

```yaml
host: http://localhost:9200
index_base_name: harmony
languages:
  - en
  - fr
  - de
  - es

# Applied at index creation only
immutable:
  number_of_shards: 1
  number_of_replicas: 0

# Tunable at runtime
mutable:
  title_boost: 2.0
  content_boost: 1.0
```

**Supported languages:** en, fr, de, es, it, pt, nl, ru, ar, zh, ja, ko

See [ES_MIGRATION.md](ES_MIGRATION.md) for migrating from a single-index setup.

## Search Pipeline Configuration

Pipeline settings are runtime-mutable — no restart needed:

```bash
# Read current config
GET /api/settings/pipeline

# Update at runtime
PATCH /api/settings/pipeline
{"reranker_enabled": true, "search_top_k": 10}
```

**Fields:**
- `keyword_candidates_n` — BM25 recall size
- `vector_top_k` — vector stage output count
- `search_top_k` — results fed to the LLM
- `vector_search_enabled` — toggle vector stage
- `reranker_enabled` — toggle reranker
- `reranker_model` — reranker model name

Defaults live in `PipelineConfig` (`harmony/api/services/_pipeline_config.py`).

To use the reranker:
```bash
ollama pull bge-reranker-v2-m3
```

To use an external Ollama instance, set `OLLAMA_HOST` and remove the `ollama` service from `docker-compose.yml`.

## Agentic Search Tuning

Resolved through `ServiceConfigStore` (ENV > DB > default) — see the [Agentic Search](#agentic-search) env vars above, or adjust at runtime via the admin UI's pipeline settings editor.

## Crawler Config (`harmony_config.yaml`)

```yaml
start_urls:
  - "https://docs.example.com"

proxy:
  url: http://proxy.example.com:8080
  username: user  # optional
  password: pass  # optional

domain_routing:
  exact:
    "docs.example.com": docs
  patterns:
    - pattern: ".*-docs\\..*"
      spider: docs
  default: generic

spider_settings:
  docs:
    skip_versions: true
    version_allowlist: [stable, latest, current]

crawler:
  safety_allow_list:
    - "example\\.com/admin/view.*"
  safety_deny_list:
    - "/private/.*"
```

For Scrapy-level settings, edit `harmony/providers/web_crawler/runtime/settings.py`.

See [INDEXING.md](INDEXING.md) for detailed indexing instructions and [CRAWLER.md](CRAWLER.md) for full crawler docs.
