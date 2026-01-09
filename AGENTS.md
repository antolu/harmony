# Harmony - Codebase Context

## Project Overview

Harmony is a fully containerized, on-premise alternative to Perplexity for LLM-powered information retrieval. Unlike RAG-based systems, Harmony uses Elasticsearch for precise search, allowing LLMs to query structured and unstructured data with multiple queries and follow-ups.

### Goal
Create a Perplexity-like experience with your own data, fully on-premise, supporting:
- **BYOLLM** or cloud LLM providers (OpenAI, Anthropic, etc.)
- **Multi-source ingestion**: Web crawlers, JIRA, Confluence, SharePoint, WordPress, Drupal, PDFs
- **Search, not RAG**: Elasticsearch-backed retrieval for accuracy
- **Chat interface**: Interactive question-answering with source citations
- **Full containerization**: Docker-based deployment

### Current Implementation (Phase 1)
The project currently includes:
1. **Web crawler** (`harmony/crawler/`) - Scrapy-based with authentication
2. **Elasticsearch indexer** (`harmony/indexer/`) - Bulk indexing with metadata

### Planned Components (Future Phases)
- **LLM orchestration layer** - Query planning, multi-search, result synthesis
- **Chat frontend** - Web UI for interactive queries
- **Data connectors** - JIRA, Confluence, SharePoint, WordPress, Drupal adapters
- **Document ingestion** - PDF, DOCX, markdown processors
- **Container orchestration** - Docker Compose for full stack deployment

## Architecture

### Crawler (`harmony/crawler/`)

**Main Components:**
- `spiders/` - Multiple spider types for different content sources:
  - `harmony.py` - Main spider with processor delegation
- `middlewares.py` - SafetyMiddleware, DomainRouterMiddleware, DeltaFetchMiddleware
- `safety.py` - Safety configuration and URL validation
- `config.py` - YAML configuration loader
- `pipelines.py` - HTML expansion and file storage pipelines
- `settings.py` - Scrapy configuration with safety defaults
- `items.py` - PageItem and DocumentItem definitions
- `cli.py` - Command-line interface with config file support
- `logger.py` - Rich logging configuration

**Safety Mechanisms:**
The crawler includes multiple layers of protection to prevent dangerous actions:

1. **HTTP Method Restriction** - Only GET and HEAD requests by default
2. **URL Pattern Blocking** - Blocks URLs with delete/edit/remove/etc paths
3. **Query Parameter Filtering** - Blocks dangerous query params (action=delete, etc)
4. **LinkExtractor Deny Patterns** - Pre-filters dangerous URLs at link extraction
5. **Safe Mode** - Extra strict mode blocks URLs with id= + action words
6. **Dry Run Mode** - Log URLs without making actual requests
7. **robots.txt Respect** - Enabled by default (can be disabled)
8. **Rate Limiting** - Auto-throttle and concurrent request limits
9. **Domain Restrictions** - Only crawls allowed domains

**Safety Configuration:**
- Default: Safe by default with protection enabled
- CLI flags:
  - `--safe-mode` - Extra strict safety checks
  - `--dry-run` - Test mode without requests
  - `--allow-mutations` - Reduce restrictions (use with caution)
  - `--ignore-robots` - Disable robots.txt (not recommended)

**Multi-Spider Architecture:**
1. All spiders start with same `start_urls`
2. `DomainRouterMiddleware` examines each request's domain
3. Tags request with `spider_type` based on config
4. Each spider only processes URLs matching its type
5. Spider-specific settings passed via `response.meta`

**Crawl Flow:**
1. Load configuration from YAML (optional) or CLI args
2. SafetyMiddleware checks all requests for dangerous patterns
3. DomainRouterMiddleware routes requests to appropriate processor
4. Extract links using `LinkExtractor` with deny patterns
5. Filter by allowed domains
6. Process page through pipelines:
   - `HTMLExpanderPipeline` - Expand `<details>` tags, remove `display:none`
   - `FileStoragePipeline` - Save HTML and append to per-domain `metadata.jsonl`
7. Follow links up to `max_depth`

**File Storage Logic:**
- URLs map to directories: `/en/home` → `domain.com/en/home/index.html`
- Version paths like `/1.1.5` saved as directories (not files with `.5` extension)
- Handles file/directory conflicts by converting files to directories
- Per-domain metadata: `domain.com/metadata.jsonl` with atomic file locking
- Preserves URL hierarchy

**Configuration (YAML):**
```yaml
start_urls:
  - "https://docs.example.com"
  - "https://admin.example.com"

domain_routing:
  exact:
    "docs.example.com": docs
    "admin.example.com": drupal
  patterns:
    - pattern: ".*-docs\\..*"
      spider: docs
  default: generic

spider_settings:
  docs:
    skip_versions: true
    version_allowlist: [stable, latest, current]
```

### Indexer (`harmony/indexer/`)

**Main Components:**
- `cli.py` - Elasticsearch bulk indexing script

**Indexing Flow:**
1. Recursively find all `metadata.jsonl` files using `rglob()`
2. For each metadata entry, resolve HTML file relative to metadata location
3. Extract title and text content (strip scripts/styles)
4. Create Elasticsearch document with metadata + content
5. Bulk index using `elasticsearch.helpers.streaming_bulk`
6. Gracefully skip missing files/directories

**Document Schema:**
```python
{
    "url": "keyword",
    "title": "text",
    "content": "text",  # Extracted from HTML
    "domain": "keyword",
    "path": "keyword",
    "depth": "integer",
    "crawled_at": "date",
    "file_path": "keyword",
    "language": "keyword"
}
```

### OpenWebUI Pipelines (`openwebui_pipelines/`)

**Main Components:**
- `harmony_search_model.py` - AI Search pipeline with tool calling
- `harmony_agentic_search.py` - Agentic multi-agent search pipeline
- `harmony_direct_search.py` - Direct Elasticsearch search pipeline

**Pipeline Architecture:**
- Type: `manifold` - Allows a pipeline to provide multiple models to OpenWebUI
- Each pipeline connects to Harmony API endpoints and proxies streaming responses

**CRITICAL: Manifold Pipelines Must Use Synchronous Generators**

OpenWebUI manifold pipelines do NOT support `async def pipe()` with `AsyncGenerator`. They require:
- Synchronous `def pipe()` (not `async def`)
- Return type: `Generator[str, None, None]` (not `AsyncGenerator`)
- Synchronous HTTP client: `httpx.Client()` (not `AsyncClient()`)
- Regular iteration: `for line in response.iter_lines()` (not `async for`)

**Problem:** Async generators get exhausted during OpenWebUI's inspection, causing empty responses. The pipelines framework iterates the generator to check if it's valid, which consumes all values before streaming to the user.

**Solution:**
```python
from collections.abc import Generator
import httpx

def pipe(self, user_message: str, model_id: str, messages: list[dict], body: dict) -> Generator[str, None, None]:
    """Synchronous generator for streaming."""
    with httpx.Client(timeout=120.0) as client:
        with client.stream("POST", f"{self.valves.harmony_api_url}/ai-search", json={"query": user_message}) as response:
            for line in response.iter_lines():
                # Parse SSE and yield plain text chunks
                yield chunk
```

**SSE to Plain Text Conversion:**
- Harmony API returns Server-Sent Events (SSE) format
- Pipelines parse SSE and yield plain text strings (not JSON)
- OpenWebUI handles formatting the plain text for display

**References:**
- [OpenWebUI Pipe Function Documentation](https://docs.openwebui.com/features/plugin/functions/pipe/)
- [Known Issue: async pipeline #411](https://github.com/open-webui/pipelines/issues/411)

## Key Design Decisions

1. **Multiple spiders with middleware routing** - Scale to many content types without code duplication
2. **Priority-based domain matching** - Exact match → regex patterns → default spider
3. **Per-domain metadata.jsonl** - Atomic writes with file locking, parallel-safe
4. **Version path detection** - Skip numeric versions (1.0, v2.1) but allow aliases (stable, latest)
5. **Scrapy over custom crawler** - Handles deduplication, retry logic, concurrency automatically
6. **Directory-based file storage** - Avoids conflicts, works with version numbers
7. **JSONL metadata** - One JSON object per line, easy for streaming and bulk import
8. **HTML expansion** - Server-side rendering support (BeautifulSoup), not browser automation
9. **Cookie authentication** - Loaded from `.env` for stateful crawling
10. **Safety by default** - Multiple layers of protection against destructive actions
11. **Defense in depth** - Pattern blocking at LinkExtractor and SafetyMiddleware levels

## Safety Best Practices

1. Never disable safety without good reason
2. Review blocked URLs before allowing (check crawler logs)
3. Use dry-run first on new sites to test safety filters
4. Keep deny patterns updated as new threats emerge
5. Test on non-production sites first
6. Use allowed_domains to limit scope
7. Respect robots.txt when possible
8. Identify as a crawler (USER_AGENT)
9. Rate limit to avoid overwhelming servers
10. Monitor safety stats after crawls complete
10. **Synchronous OpenWebUI pipelines** - Manifold pipes must use `def pipe()` with `Generator`, not async
11. **Server-Sent Events (SSE) for streaming** - Real-time event streaming from API to pipelines to UI

## Configuration

- **Crawler config**: `harmony_config.yaml` (optional) - Domain routing, spider settings
- **Scrapy settings**: `harmony/crawler/settings.py` - Global crawler settings
- **Elasticsearch**: `docker-compose.yml` - Single-node cluster with Kibana

## Dependencies

- `scrapy >= 2.11.0` - Web crawling framework
- `beautifulsoup4 >= 4.12.0` - HTML parsing
- `lxml >= 5.0.0` - Fast XML/HTML parser
- `python-dotenv >= 1.0.0` - Environment variable loading
- `rich >= 13.0.0` - Console logging
- `pyyaml >= 6.0.0` - YAML configuration parsing
- `langdetect >= 1.0.9` - Language detection
- `elasticsearch >= 8.0.0` - (optional) Elasticsearch client

## Entry Points

- `harmony-crawl` → `harmony.crawler.cli:main`
- `harmony-index` → `harmony.indexer.cli:main`

## Usage Examples

**Crawl with YAML config:**
```bash
harmony-crawl --config harmony_config.yaml --output output/
```

**Crawl with CLI args (no config):**
```bash
harmony-crawl --start-urls https://example.com --output output/ --max-depth 10
```

**Crawl with safety flags:**
```bash
# Extra safe mode
harmony-crawl --config config.yaml --output data/ --safe-mode

# Dry run (test without requests)
harmony-crawl --config config.yaml --output data/ --dry-run

# Allow mutations (use with caution)
harmony-crawl --config config.yaml --output data/ --allow-mutations
```

**Index crawled data:**
```bash
harmony-index --data-dir output/ --es-host http://localhost:9200 --index-name harmony
```

## Common Patterns

**Adding a new spider type:**
1. Create `harmony/crawler/spiders/newtype.py` extending `CrawlSpider`
2. Add spider type check: `if response.meta.get("spider_type") != "newtype": return`
3. Update config YAML to route domains to `newtype`

**Adding domain routing:**
Edit `harmony_config.yaml`:
```yaml
domain_routing:
  exact:
    "docs.example.com": docs
  patterns:
    - pattern: ".*\\.example\\.com"
      spider: generic
```

**Adding version filtering for docs:**
Edit config YAML:
```yaml
spider_settings:
  docs:
    skip_versions: true
    version_allowlist: [stable, latest, v1, v2]
```

**Modifying HTML expansion:**
Edit `HTMLExpanderPipeline.process_item()` in `harmony/crawler/pipelines.py`

**Changing Elasticsearch mapping:**
Edit `index_settings` in `harmony/indexer/cli.py:main()`
