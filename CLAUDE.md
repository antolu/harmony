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
  - `drupal.py` - Drupal sites (formerly admin_eguide.py)
  - `docs.py` - Documentation sites with version filtering
  - `generic.py` - Fallback spider for general sites
- `middlewares.py` - DomainRouterMiddleware for spider routing
- `config.py` - YAML configuration loader
- `pipelines.py` - HTML expansion and file storage pipelines
- `settings.py` - Scrapy configuration with .env cookie loading
- `items.py` - PageItem definition (url, html, depth)
- `cli.py` - Command-line interface with config file support
- `logger.py` - Rich logging configuration

**Multi-Spider Architecture:**
1. All spiders start with same `start_urls`
2. `DomainRouterMiddleware` examines each request's domain
3. Tags request with `spider_type` (drupal/docs/generic) based on config
4. Each spider only processes URLs matching its type
5. Spider-specific settings passed via `response.meta`

**Crawl Flow:**
1. Load configuration from YAML (optional) or CLI args
2. Start all spiders (drupal, docs, generic) with same URLs
3. Middleware routes each request to appropriate spider
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

**Crawl mixed (config + extra URLs):**
```bash
harmony-crawl --config harmony_config.yaml --start-urls https://extra.com
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
