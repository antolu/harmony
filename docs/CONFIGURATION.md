# Configuration

## Environment Variables

### LLM Provider

Provide a key for whichever provider you use:

```bash
GEMINI_API_KEY=your_key
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key

# Model selection — see https://docs.litellm.ai/docs/providers for all options
LLM_MODEL=gemini/gemini-3-flash-preview

# Examples:
#   Gemini:    gemini/gemini-3-flash-preview, gemini/gemini-3-pro
#   OpenAI:    gpt-4, gpt-4-turbo, gpt-3.5-turbo
#   Anthropic: claude-3-5-sonnet-20241022, claude-3-opus-20240229
#   Ollama:    ollama_chat/llama3, ollama_chat/mistral

# Ollama (bundled in docker-compose; override to use your own)
OLLAMA_HOST=http://localhost:11434
```

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
QDRANT_COLLECTION=harmony
QDRANT_VECTOR_SIZE=512          # Must match embedding model output
EMBEDDING_MODEL=ollama/qwen3-embedding:0.6b
EMBEDDING_BATCH_SIZE=64
```

### Document Cache

```bash
DOCUMENT_CACHE_ENABLED=true
DOCUMENT_CACHE_TTL=3600         # seconds
DOCUMENT_CACHE_MAX_SIZE=1000
```

### Agentic Search

```bash
AGENTIC_MAX_REFINEMENT_ROUNDS=3
AGENTIC_MAX_QUERY_VARIANTS=4
AGENTIC_SEARCH_TOP_K=10
AGENTIC_MAX_SOURCES_RETURNED=10
```

### MCP Servers

```bash
MCP_SERVERS='[
  {
    "name": "filesystem",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/directory"],
    "env": {}
  },
  {
    "name": "github",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": {
      "GITHUB_PERSONAL_ACCESS_TOKEN": "your_token"
    }
  }
]'
```

Fields: `name` (identifier), `command` (executable), `args` (command arguments), `env` (environment variables).

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
GET /settings/pipeline

# Update at runtime
PATCH /settings/pipeline
{"reranker_enabled": true, "search_top_k": 10}
```

**Fields:**
- `keyword_candidates_n` — BM25 recall size
- `vector_top_k` — vector stage output count
- `search_top_k` — results fed to the LLM
- `vector_search_enabled` — toggle vector stage
- `reranker_enabled` — toggle reranker
- `reranker_model` — reranker model name

Defaults live in `PipelineConfig` (`harmony/api/services/pipeline_config.py`).

To use the reranker:
```bash
ollama pull bge-reranker-v2-m3
```

To use an external Ollama instance, set `OLLAMA_HOST` and remove the `ollama` service from `docker-compose.yml`.

## Agentic Search Tuning

Adjust in `harmony/api/config.py` or via environment variables (see [Environment Variables](#agentic-search) above):

```python
agentic_max_refinement_rounds: int = 3
agentic_max_query_variants: int = 4
agentic_search_top_k: int = 10
agentic_max_sources_returned: int = 10
```

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

For Scrapy-level settings, edit `harmony/crawler/settings.py`.

See [INDEXING.md](INDEXING.md) for detailed indexing instructions and [CRAWLER.md](CRAWLER.md) for full crawler docs.
