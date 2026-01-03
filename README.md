# Harmony

> The opposite of Perplexity - Your own on-premise LLM-powered information retrieval system

Harmony is a fully containerized solution for creating a Perplexity-like experience with your own data. It uses Elasticsearch as a search backend to enable LLMs to query your knowledge base without RAG, providing accurate, source-cited answers from your internal documents and data.

## Vision

A complete on-premise alternative to Perplexity that:
- **Searches, not embeds** - Uses Elasticsearch for precise information retrieval, not RAG
- **Bring Your Own LLM** - Works with local models or cloud providers (OpenAI, Anthropic, etc.)
- **Multi-source ingestion** - Crawlers and connectors for web, JIRA, Confluence, SharePoint, WordPress, Drupal, PDFs, and more
- **Fully containerized** - Deploy anywhere with Docker
- **Privacy-first** - Keep your data on-premise

## Current Status

✅ **Web Crawler & Indexer** (Phase 1)
- Scrapy-based crawler with authentication
- HTML content expansion
- Elasticsearch indexing with metadata
- Configurable filtering and depth control

🚧 **Coming Soon**
- LLM orchestration layer with multi-query support
- Chat frontend interface
- Additional data connectors (JIRA, Confluence, SharePoint, etc.)
- PDF and document ingestion
- Docker Compose orchestration for full stack

## Current Features

- **Scrapy-based crawler** with authentication support
- **HTML content expansion** - Opens collapsed/hidden elements
- **Hierarchical file storage** - Maintains source URL structure
- **Metadata tracking** - JSONL format for easy ingestion
- **Elasticsearch indexing** - Full-text search capabilities
- **Configurable filtering** - Domain restrictions, URL pattern exclusion
- **Progress tracking** - Rich console logging

## Installation

```bash
pip install -e .

# For Elasticsearch indexing
pip install -e ".[elasticsearch]"

# For browser automation (JS-heavy sites)
pip install -e ".[browser]"
```

## Usage

### 1. Crawling

```bash
harmony-crawl \
  --start-urls https://example.com/en https://example.com/fr \
  --output crawled_data \
  --max-depth 100 \
  --delay 1.0 \
  --concurrent 5
```

**Options:**
- `--start-urls` - URLs to start crawling from (required)
- `--allowed-domains` - Additional domains to allow (auto-includes start URL domains)
- `--output` - Output directory (default: `output`)
- `--max-depth` - Maximum crawl depth (default: 100)
- `--delay` - Delay between requests in seconds (default: 1.0)
- `--concurrent` - Max concurrent requests (default: 5)
- `--verbose` - Enable debug logging

### 2. Authentication

Create a `.env` file with cookies:

```bash
# .env
CERN_COOKIE=your_cookie_value_here
```

### 3. Elasticsearch Indexing

Start Elasticsearch:

```bash
docker compose up -d
```

Index the crawled data:

```bash
harmony-index \
  --data-dir output \
  --es-host http://localhost:9200 \
  --index-name my-index
```

Access Kibana UI at http://localhost:5601

## Output Structure

```
output/
├── metadata.jsonl          # Document metadata for Elasticsearch
├── crawler.log             # Crawl logs
└── domain.com/
    └── path/to/page/
        └── index.html      # Saved HTML files
```

## Link Filtering

The crawler automatically excludes:
- Authentication URLs (`auth.cern.ch`)
- Logout/sign-out links
- JavaScript URLs (`javascript:`)
- Drupal node IDs (`/node/\d+`)

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run pre-commit checks
pre-commit run --all-files
```

## Configuration

Edit `harmony/crawler/settings.py` for Scrapy settings.

See `INDEXING.md` for detailed Elasticsearch indexing instructions.
