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
- `spiders/admin_eguide.py` - CrawlSpider with link extraction rules
- `pipelines.py` - HTML expansion and file storage pipelines
- `settings.py` - Scrapy configuration with .env cookie loading
- `items.py` - PageItem definition (url, html, depth)
- `cli.py` - Command-line interface for crawling
- `logger.py` - Rich logging configuration

**Crawl Flow:**
1. Start from `start_urls` with depth 0
2. Extract links using `LinkExtractor` with deny patterns
3. Filter by allowed domains
4. Process page through pipelines:
   - `HTMLExpanderPipeline` - Expand `<details>` tags, remove `display:none`
   - `FileStoragePipeline` - Save HTML and append metadata to `metadata.jsonl`
5. Follow links up to `max_depth`

**File Storage Logic:**
- URLs map to directories: `/en/home` → `en/home/index.html`
- Handles file/directory conflicts by converting files to directories with `index.html`
- Preserves URL hierarchy

### Indexer (`harmony/indexer/`)

**Main Components:**
- `cli.py` - Elasticsearch bulk indexing script

**Indexing Flow:**
1. Read `metadata.jsonl` line by line
2. Load corresponding HTML file
3. Extract title and text content (strip scripts/styles)
4. Create Elasticsearch document with metadata + content
5. Bulk index using `elasticsearch.helpers.streaming_bulk`

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
    "file_path": "keyword"
}
```

## Key Design Decisions

1. **Scrapy over custom crawler** - Handles deduplication, retry logic, concurrency automatically
2. **Directory-based file storage** - Avoids conflicts when `/en` and `/en/home` both exist
3. **JSONL metadata** - One JSON object per line, easy for streaming and bulk import
4. **HTML expansion** - Server-side rendering support (BeautifulSoup), not browser automation
5. **Cookie authentication** - Loaded from `.env` for stateful crawling

## Configuration

- **Scrapy settings**: `harmony/crawler/settings.py`
- **Link filtering**: `harmony/crawler/spiders/admin_eguide.py` - `deny` patterns
- **Elasticsearch**: `docker-compose.yml` - Single-node cluster with Kibana

## Dependencies

- `scrapy >= 2.11.0` - Web crawling framework
- `beautifulsoup4 >= 4.12.0` - HTML parsing
- `lxml >= 5.0.0` - Fast XML/HTML parser
- `python-dotenv >= 1.0.0` - Environment variable loading
- `rich >= 13.0.0` - Console logging
- `elasticsearch >= 8.0.0` - (optional) Elasticsearch client

## Entry Points

- `harmony-crawl` → `harmony.crawler.cli:main`
- `harmony-index` → `harmony.indexer.cli:main`

## Testing

Run crawl with limited depth to test:
```bash
harmony-crawl --start-urls https://example.com --output test_output --max-depth 1 --verbose
```

## Common Patterns

**Adding new link exclusion:**
Edit `harmony/crawler/spiders/admin_eguide.py`:
```python
deny=(
    r"auth\.cern\.ch",
    r"/node/\d+",
    r"your_pattern_here",  # Add here
)
```

**Modifying HTML expansion:**
Edit `HTMLExpanderPipeline.process_item()` in `harmony/crawler/pipelines.py`

**Changing Elasticsearch mapping:**
Edit `index_settings` in `harmony/indexer/cli.py:main()`
