# Configuration Reference

## Environment Variables

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

See <https://docs.litellm.ai/docs/providers> for all supported models.

**Elasticsearch:**

```bash
# Use config file (recommended)
ES_CONFIG_FILE=configs/es_config.yaml

# Or individual settings
ES_HOST=http://localhost:9200
ES_INDEX_BASE_NAME=harmony
ES_LANGUAGES=en,fr,de,es
```

**Qdrant / embeddings:**

```bash
QDRANT_HOST=http://localhost:6333
QDRANT_COLLECTION=harmony
QDRANT_VECTOR_SIZE=512          # Must match embedding model output (qwen3-embedding:0.6b = 512)
EMBEDDING_MODEL=ollama/qwen3-embedding:0.6b
EMBEDDING_BATCH_SIZE=64
```

**Search pipeline:**

Pipeline settings (`keyword_candidates_n`, `vector_top_k`, `search_top_k`, `vector_search_enabled`, `reranker_enabled`, `reranker_model`) are managed at runtime via `PATCH /settings/pipeline` and read via `GET /settings/pipeline`. Defaults live in `PipelineConfig` (`harmony/api/services/_pipeline_config.py`).

To enable the reranker, pull the model first: `ollama pull bge-reranker-v2-m3`

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

## YAML Configuration

**Crawler config (`harmony_config.yaml`):**

```yaml
start_urls:
  - "https://docs.example.com"

# Proxy (optional)
proxy:
  url: http://proxy.example.com:8080 # Scheme determines type (http/https/socks4/socks5)
  username: user # optional
  password: pass # optional

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

**Elasticsearch config (`configs/es_config.yaml`):**

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
