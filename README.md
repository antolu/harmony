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

[DONE] **Phase 1: Web Crawler & Indexer**
- Scrapy-based crawler with authentication
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

[TODO] **Coming Soon**
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
                                    │   Elasticsearch         │
                                    │   (Knowledge Base)      │
                                    └─────────────────────────┘
```

### Agentic Search Architecture

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

## Features

### Data Ingestion
- **Scrapy-based crawler** with authentication support
- **Document parsing** - PDF, DOCX, XLSX, ODT, TXT, CSV extraction
- **HTML content expansion** - Opens collapsed/hidden elements
- **Safety mechanisms** - Multiple layers to prevent destructive actions
- **Stateful crawling** - Change detection with HTTP headers and SHA256 hashing
- **Deletion tracking** - Grace period before removing missing content
- **Pause/resume** - Continue interrupted crawls with jobdir
- **Age-based re-crawling** - Only crawl stale content
- **Proxy support** - HTTP/HTTPS/SOCKS4/SOCKS5 with authentication
- **Hierarchical file storage** - Maintains source URL structure
- **Metadata tracking** - JSONL format for easy ingestion
- **Elasticsearch indexing** - Full-text search with language detection
- **Deletion sync** - Keep search index synchronized with crawled content
- **Configurable filtering** - Domain restrictions, URL pattern exclusion
- **Progress tracking** - Rich console logging

### LLM-Powered Search
- **Direct Search** - Fast Elasticsearch queries with Google-like formatting
- **AI Search** - Streaming agentic loop with tool calling for iterative refinement
- **Agentic Search** - Multi-agent orchestration with:
  - Query planning (2-4 diverse search variants) - streamed as generated
  - Parallel search execution - "Reading [page]" events for each source
  - Critic-synthesizer refinement loop (k=3 rounds) - round status streaming
  - Real-time answer token streaming
  - Consensus detection for early stopping
  - Source citation and answer quality validation

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Run pre-commit checks manually
pre-commit run --all-files
```

## Roadmap
- `GET /search?q=query` - Direct Elasticsearch search
- `POST /ai-search` - Streaming AI-powered search with tool calling
- `POST /agentic-search` - Streaming Agentic multi-agent search
- `GET /health` - Health check endpoint
- `GET /docs` - OpenAPI documentation

All search endpoints return Server-Sent Events (SSE) with real-time streaming:
- `query_variant` - Each search variant as it's generated
- `reading_page` - Once per unique page title during search
- `refinement_round` - Round start/complete with consensus status
- `answer_chunk` - Answer tokens in real-time
- `tool_call` - Tool execution events (AI Search)
- `done` - Final metadata (sources, rounds, variants)
- `error` - Error messages

### OpenWebUI Integration
- **Direct Search Pipeline** - Fast keyword search with formatted results
- **AI Search Pipeline** - Intelligent search with follow-up queries and streaming
- **Agentic Search Pipeline** - Multi-agent collaborative search with live progress

## Installation

```bash
pip install -e .

# For Elasticsearch indexing
pip install -e ".[elasticsearch]"

# For browser automation (JS-heavy sites)
pip install -e ".[browser]"
```

## Quick Start

### Full Stack (Recommended)

```bash
# Create .env file with your API keys
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Start all services
docker compose up -d

# Services will be available at:
# - OpenWebUI: http://localhost:3000
# - Harmony API: http://localhost:8000
# - Elasticsearch: http://localhost:9200
# - Kibana: http://localhost:5601
# - Pipelines: http://localhost:9099
```

Access OpenWebUI at http://localhost:3000 and select one of the Harmony search pipelines.

## Usage

### 1. Web Crawling

```bash
harmony-crawl \
  --crawler.start_urls+ https://example.com/en https://example.com/fr \
  --crawler.output crawled_data \
  --crawler.max_depth 100 \
  --crawler.delay 1.0 \
  --crawler.concurrent 5
```

**Common Options:**
- `--crawler.start_urls+` - URLs to start crawling from (required, use `+` to append multiple)
- `--crawler.allowed_domains+` - Additional domains to allow
- `--crawler.output` - Output directory (default: `output`)
- `--crawler.max_depth` - Maximum crawl depth (default: 100)
- `--crawler.delay` - Delay between requests in seconds (default: 1.0)
- `--crawler.concurrent` - Max concurrent requests (default: 5)
- `--crawler.verbose` - Verbosity level (0-3, default: 0)
- `--print-config` - Print full resolved configuration and exit
- `--help` - Show all available options

**Safety Options:**
- `--crawler.safe_mode` - Extra strict safety checks (blocks URLs with id= + action words)
- `--crawler.dry_run` - Test mode without making actual requests
- `--crawler.allow_mutations` - Reduce safety restrictions (use with caution)
- `--crawler.ignore_robots` - Disable robots.txt respect (not recommended)

### 2. Configuration File (Recommended)

Create a `harmony_config.yaml` file to configure domain routing and spider settings:

```yaml
start_urls:
  - "https://docs.example.com"
  - "https://admin.example.com"

# Proxy configuration (optional)
proxy:
  url: http://proxy.example.com:8080  # Scheme determines type
  username: user  # optional
  password: pass  # optional

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

Use with:
```bash
harmony-crawl --config harmony_config.yaml --output output/
```

**Safety Features:**

The crawler includes multiple layers of protection to prevent destructive actions:

- **HTTP Method Restriction** - Only GET and HEAD requests by default
- **URL Pattern Blocking** - Blocks URLs containing delete, edit, remove, submit, etc.
- **Query Parameter Filtering** - Blocks dangerous params like `action=delete`
- **Safe Mode** - Extra strict checks for URLs with id parameters and action words
- **Dry Run Mode** - Test crawling without making actual requests
- **robots.txt Respect** - Enabled by default (can be disabled with caution)
- **Rate Limiting** - Auto-throttle prevents overwhelming servers

**Safety Examples:**

```bash
# Extra safe mode (recommended for unknown sites)
harmony-crawl --config config.yaml --crawler.safe_mode

# Test crawl without making requests
harmony-crawl --config config.yaml --crawler.dry_run

# Allow mutation endpoints (use with extreme caution)
harmony-crawl --config config.yaml --crawler.allow_mutations
```

After a crawl, check the logs for safety statistics:
```
[SAFETY STATS] Blocked 47 potentially dangerous requests:
  - Matched dangerous pattern: /delete/: 23
  - Matched dangerous pattern: /edit/: 15
  - Dangerous query param: action=delete: 9
```

**Proxy Support:**
- **HTTP/HTTPS proxy** - Use `http://` or `https://` URL scheme
- **SOCKS4/SOCKS5 proxy** - Use `socks4://` or `socks5://` URL scheme
- Authentication supported for all proxy types via optional `username` and `password` fields

### 3. Authentication

Create a `.env` file with cookies:

```bash
# .env
CERN_COOKIE=your_cookie_value_here
```

### 4. Elasticsearch Indexing

Start Elasticsearch:

```bash
docker compose up -d
```

Index the crawled data:

```bash
harmony-index \
  --data-dir output \
  --es-host http://localhost:9200 \
  --index-name harmony
```

Access Kibana UI at http://localhost:5601

## Crawler Safety

Harmony's crawler is designed with safety as a priority to prevent destructive actions during crawling.

### Safety Mechanisms

1. **HTTP Method Restriction**
   - Only GET and HEAD requests allowed by default
   - POST, PUT, DELETE, PATCH are blocked

2. **Dangerous URL Pattern Detection**
   - Blocks URLs with destructive keywords: `/delete/`, `/remove/`, `/destroy/`, `/purge/`
   - Blocks mutation endpoints: `/edit/`, `/update/`, `/modify/`, `/change/`
   - Blocks form actions: `/submit`, `/cancel`
   - Blocks auth actions: `/logout`, `/signout`, `/sign-out`
   - Blocks admin mutations: `/admin/.*/delete`, `/admin/.*/edit`

3. **Query Parameter Filtering**
   - Blocks dangerous params: `action=delete`, `method=POST`, `confirm=yes`
   - Blocks submit params: `submit=yes`, `cancel=yes`

4. **Safe Mode (--crawler.safe_mode)**
   - Extra strict checks
   - Blocks URLs with `id=` parameter combined with action words
   - Example: blocks `https://site.com/edit?id=123`

5. **Dry Run Mode (--crawler.dry_run)**
   - Logs URLs without making requests
   - Perfect for testing safety filters on new sites

6. **Defense in Depth**
   - LinkExtractor deny patterns (early filtering)
   - SafetyMiddleware (runtime protection)
   - Allow-list support for trusted URLs

### Safety Best Practices

1. **Always test new sites with dry-run first:**
   ```bash
   harmony-crawl --config config.yaml --crawler.dry_run
   ```

2. **Review blocked URLs in logs:**
   ```
   [SAFETY BLOCK] https://example.com/admin/delete/123
     Reason: Matched dangerous pattern: /delete/
     Method: GET
     Referer: https://example.com/admin/users
   ```

3. **Use safe mode for unknown or admin sites:**
   ```bash
   harmony-crawl --config config.yaml --crawler.safe_mode
   ```

4. **Only disable safety when absolutely necessary:**
   ```bash
   # Use with extreme caution!
   harmony-crawl --config config.yaml --crawler.allow_mutations
   ```

5. **Monitor safety statistics after each crawl:**
   - Check crawler logs for `[SAFETY STATS]` summary
   - Review patterns that were blocked
   - Adjust configuration if legitimate URLs were blocked

6. **Use allowed_domains to limit scope:**
   ```yaml
   allowed_domains:
     - docs.example.com
     - help.example.com
   ```

7. **Respect robots.txt (enabled by default):**
   - Only disable with `--crawler.ignore_robots` if you have permission

### Interactive Safety Mode

Enable interactive prompts to build your allow/deny lists:

```bash
harmony-crawl --config config.yaml --crawler.interactive_safety true
```

When a URL is blocked, you'll be prompted:

```
⚠ URL BLOCKED BY SAFETY
URL: https://example.com/admin/edit/123
Reason: Matched dangerous pattern: /edit/
Pattern: example\.com/admin/edit/\d+

Allow this URL? [y/N/always/never]:
  y       - Allow this once
  N       - Deny this once (default)
  always  - Add pattern to permanent allow-list
  never   - Add pattern to permanent deny-list
```

Patterns are saved to `.harmony-safety-lists.json` and persist across runs.

### Custom Allow/Deny Lists

**Via config file:**
```yaml
crawler:
  safety_allow_list:
    - "example\\.com/special/edit.*"  # Allow specific edit pages
    - "docs\\.example\\.com/.*"        # Allow docs subdomain

  safety_deny_list:
    - "/private/.*"      # Block private paths
    - ".*\\?debug=.*"    # Block debug params
```

**Via CLI:**
```bash
harmony-crawl --config config.yaml \
  --crawler.safety_allow_list+ "example\\.com/admin/view.*" \
  --crawler.safety_deny_list+ "/sensitive/.*"
```

### Persistent Lists File

The `.harmony-safety-lists.json` file stores learned patterns:

```json
{
  "allow_patterns": [
    "example\\.com/admin/view/\\d+",
    "docs\\.example\\.com/.*"
  ],
  "deny_patterns": [
    "/private/.*",
    ".*\\?debug=.*"
  ],
  "metadata": {
    "last_updated": "2026-01-08T12:34:56"
  }
}
```

You can edit this file manually to manage patterns.

### Customizing Safety Rules

You can customize safety rules via configuration:

```python
# In your config or code
from harmony.crawler.safety import SafetyConfig

custom_safety = SafetyConfig(
    # Add custom deny patterns
    additional_deny_patterns=[
        r"/admin/.*",
        r"/private/.*"
    ],
    # Allow specific URLs that would otherwise be blocked
    allow_list_patterns=[
        r"example\.com/admin/view/.*"  # Read-only admin pages
    ],
    # Enable extra strict mode
    safe_mode=True
)
```

## Crawl State Management

Harmony supports stateful crawling with change detection and deletion tracking to optimize re-crawls and keep your search index synchronized.

### Two Elasticsearch Indices

**1. Content Index** (`harmony`)
- Stores searchable content for LLM queries
- Contains: url, title, content, domain, path, language
- Managed by: `harmony-index` command

**2. State Index** (`harmony-crawl-state`)
- Tracks crawl metadata for optimization
- Contains: url, content_hash, last_modified, etag, last_crawled_at, missing_count
- Managed by: `harmony-crawl` command (when state tracking enabled)

### Stateless vs Stateful Modes

**Stateless Mode (default):**
- No Elasticsearch required
- Always downloads all content
- No change detection
- Good for: testing, one-off crawls

**Stateful Mode (requires Elasticsearch):**
- Enabled with `--crawler.es_state_host`
- HTTP-based change detection (If-Modified-Since, ETag)
- SHA256 hash comparison for content changes
- Deletion tracking with grace period
- Age-based re-crawling support

### Basic Stateful Workflow

**1. Initial crawl with state tracking:**
```bash
harmony-crawl \
  --config harmony_config.yaml \
  --crawler.es_state_host http://localhost:9200
```

**2. Re-crawl (automatically skips unchanged content):**
```bash
harmony-crawl \
  --config harmony_config.yaml \
  --crawler.es_state_host http://localhost:9200
```

**3. Index with deletion sync:**
```bash
harmony-index \
  --data-dir output \
  --es-host http://localhost:9200 \
  --index-name harmony \
  --sync-deletions \
  --missing-threshold 3
```

### Change Detection Flow

1. **Crawler requests URL** with `If-Modified-Since` and `If-None-Match` headers
2. **Server responds:**
   - `304 Not Modified` → Skip download, update `last_seen_at`
   - `200 OK` → Download, compute SHA256 hash
3. **Hash comparison:**
   - Hash matches → Skip file write, update `last_seen_at`
   - Hash differs → Write file, update state, update content index
4. **404/410 responses** → Increment `missing_count` in state

### Deletion Sync Flow

1. **Crawler** tracks missing URLs across multiple crawls
   - Each 404/410 increments `missing_count` in state index
   - After threshold (default 3), URL is marked for deletion

2. **Indexer** syncs deletions to content index
   - Queries state index for `missing_count >= 3`
   - Deletes those URLs from content index (`harmony`)
   - Keeps search results clean and accurate

### Advanced Features

**Pause and Resume:**
```bash
# Start crawl
harmony-crawl --config config.yaml --crawler.jobdir .crawl-state

# Interrupt with Ctrl+C, then resume
harmony-crawl --config config.yaml --crawler.jobdir .crawl-state
```

**Age-based Re-crawling:**
```bash
harmony-crawl \
  --config config.yaml \
  --crawler.es_state_host http://localhost:9200 \
  --crawler.recrawl_mode age-based \
  --crawler.max_age_days 7
```
Only re-crawls URLs older than 7 days.

**Auto-delete Missing URLs:**
```bash
harmony-crawl \
  --config config.yaml \
  --crawler.es_state_host http://localhost:9200 \
  --crawler.delete_missing true \
  --crawler.missing_threshold 3
```

### Configuration Example

```yaml
crawler:
  start_urls:
    - "https://docs.example.com"

  # State management (optional)
  es_state_host: http://localhost:9200
  es_state_index: harmony-crawl-state

  # Pause/resume (works with or without state)
  jobdir: .crawl-state

  # Re-crawling strategy
  recrawl_mode: full  # or "age-based"
  max_age_days: 7

  # Deletion management
  delete_missing: false
  missing_threshold: 3
```

### Performance Benefits

- **Bandwidth savings:** 304 responses avoid re-downloading unchanged content
- **Storage savings:** Hash comparison skips writing duplicate files
- **Time savings:** Age-based mode only crawls stale content
- **Index accuracy:** Deletion sync removes outdated content automatically

### 5. Using the API

**Direct Search:**
```bash
curl "http://localhost:8000/search?q=your+query"
```

**AI Search (streaming with tool calling):**
```bash
curl -N -X POST http://localhost:8000/ai-search \
  -H "Content-Type: application/json" \
  -d '{"query": "What is CERN?"}'
```

**Agentic Search (multi-agent streaming):**
```bash
curl -N -X POST http://localhost:8000/agentic-search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is CERN?",
    "max_refinement_rounds": 3
  }'
```

Note: Use `-N` flag with curl to disable buffering and see streaming events in real-time.

**Health Check:**
```bash
curl http://localhost:8000/health
```

### 5. Using OpenWebUI Pipelines

1. Access OpenWebUI at http://localhost:3000
2. Select a model from the dropdown:
   - **Direct Search** - Fast keyword search
   - **AI Search (Gemini)** - Intelligent LLM-powered search with streaming
   - **Agentic Search** - Multi-agent collaborative search with live progress
3. Ask questions about your indexed data and watch answers stream in real-time

### 6. Adding MCP Servers

Harmony supports [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) servers to extend the LLM with additional tools.

Add MCP servers to your `.env` file:

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

**Fields:**
- `name` - Server identifier
- `command` - Executable (e.g., `npx`, `python`, `node`)
- `args` - Command arguments
- `env` - Environment variables

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

The crawler automatically excludes dangerous and unnecessary URLs:

**Safety Filters:**
- Delete/remove/destroy actions (`/delete/`, `/remove/`, `/destroy/`)
- Edit/update/modify actions (`/edit/`, `/update/`, `/modify/`)
- Form submissions (`/submit`, `?submit=`, `?action=delete`)
- Authentication URLs (`/logout`, `/signout`, `/sign-out`)
- Admin mutations (`/admin/.*/delete`, `/admin/.*/edit`)
- API mutations (`/api/.*/delete`, `/api/.*/update`)

**Technical Filters:**
- JavaScript URLs (`javascript:`)
- Authentication domains (`auth.cern.ch`)

These filters work at both the LinkExtractor level (early filtering) and SafetyMiddleware level (defense in depth).

## Development

### Setup

```bash
# Install dev dependencies
pip install -e ".[dev,test]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

The test suite includes different categories of tests controlled by pytest markers.

**By default, only unit tests run** (no external dependencies):

```bash
# Run default tests (unit tests only)
pytest tests/

# Explicitly run only unit tests
pytest tests/ -m "not llm and not elasticsearch and not integration"
```

**To run tests with external dependencies, explicitly include them:**

```bash
# Run with Elasticsearch tests (requires ES running)
pytest tests/ -m "elasticsearch or (not llm and not integration)"

# Run with LLM tests (requires API keys)
pytest tests/ -m "llm or (not elasticsearch and not integration)"

# Run integration tests (requires all services)
pytest tests/ -m "integration"

# Run ALL tests including external dependencies
pytest tests/ -m ""

# Or override default markers
pytest tests/ --override-ini="addopts="
```

**Other useful commands:**

```bash
# Run specific test file
pytest tests/test_conversation.py -v

# Run with coverage
pytest --cov=harmony tests/

# Verbose output
pytest tests/ -v
```

**Test Markers:**
- `@pytest.mark.llm` - Tests requiring real LLM API calls (opt-in)
- `@pytest.mark.elasticsearch` - Tests requiring Elasticsearch connection (opt-in)
- `@pytest.mark.integration` - Tests requiring external services running (opt-in)

Default behavior: Only unit tests run unless explicitly requested.

### Code Quality

```bash
# Linting
ruff check --fix --unsafe-fixes --preview .

# Type checking
mypy harmony/
```

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Elasticsearch
ES_HOST=http://localhost:9200
ES_INDEX=admin-eguide

# Gemini API (or use Ollama for local LLM)
GEMINI_API_KEY=your_api_key_here
LLM_MODEL=gemini/gemini-3-flash-preview

# Ollama (optional, for local LLM)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3

# API Server
API_HOST=0.0.0.0
API_PORT=8000
```

### Agentic Search Configuration

Adjust in `harmony/api/config.py` or via environment variables:

```python
# Maximum refinement rounds in Agentic search
agentic_max_refinement_rounds: int = 3

# Maximum query variants to generate
agentic_max_query_variants: int = 4

# Top-k search results per query
agentic_search_top_k: int = 10

# Maximum sources returned in response
agentic_max_sources_returned: int = 10
```

Environment variables:
```bash
AGENTIC_MAX_REFINEMENT_ROUNDS=3
AGENTIC_MAX_QUERY_VARIANTS=4
AGENTIC_SEARCH_TOP_K=10
AGENTIC_MAX_SOURCES_RETURNED=10
```

### Crawler Configuration

Edit `harmony/crawler/settings.py` for Scrapy settings.

See `INDEXING.md` for detailed Elasticsearch indexing instructions.

## Technology Stack

### Backend
- **FastAPI** - Modern async web framework
- **LiteLLM** - Universal LLM API (supports Gemini, OpenAI, Anthropic, Ollama, etc.)
- **Elasticsearch 9.x** - Search and indexing
- **Scrapy** - Web crawling framework
- **BeautifulSoup** - HTML parsing and expansion

### Frontend & Integration
- **OpenWebUI** - Chat interface
- **OpenWebUI Pipelines** - Custom pipeline integration

### Multi-Agent System
- **Custom Agent Framework** - BaseAgent with 4 specialized agents:
  - QueryPlannerAgent (LLM-based query decomposition)
  - SearcherAgent (Elasticsearch wrapper)
  - CriticAgent (Answer validation and feedback)
  - SynthesizerAgent (Answer generation and refinement)
- **Agentic Orchestrator** - Coordinates multi-agent workflow with streaming
- **K-Round Refinement** - Iterative improvement loop with real-time updates

### Infrastructure
- **Docker Compose** - Full-stack orchestration
- **Python 3.13** - Latest Python features
- **AsyncIO** - Concurrent agent execution

## Roadmap

### [Current Focus]
- [x] Web crawler with authentication
- [x] Elasticsearch indexing
- [x] Direct search endpoint
- [x] AI-powered search with tool calling
- [x] Agentic multi-agent search with streaming
- [x] Real-time Server-Sent Events (SSE) streaming
- [x] OpenWebUI integration with streaming pipelines
- [x] Docker Compose deployment

### [Next Steps]

#### Data Connectors
- [ ] JIRA connector
- [ ] Confluence connector
- [ ] SharePoint connector
- [ ] WordPress connector
- [ ] Drupal connector
- [ ] Generic REST API connector

#### Document Processing
- [ ] PDF ingestion with text extraction
- [ ] DOCX document processing
- [ ] Markdown file ingestion
- [ ] Code repository indexing

#### Advanced Features
- [ ] FAISS-based capability matching for agent selection
- [ ] Embedding service for semantic search
- [ ] Multi-turn conversation support
- [ ] Query history and analytics
- [ ] Result caching and optimization
- [ ] Custom agent plugins system

#### Enterprise Features
- [ ] User authentication and authorization
- [ ] Multi-tenant support
- [ ] Audit logging
- [ ] Rate limiting
- [ ] Admin dashboard
- [ ] Monitoring and metrics

#### Quality & Performance
- [ ] Comprehensive unit tests for all agents
- [ ] Performance benchmarking
- [ ] Memory optimization for large datasets
- [ ] Distributed agent execution
- [ ] Result quality metrics

## License

Other/Proprietary License - See LICENSE file for details.

## Acknowledgments

- Inspired by the [Federation of Agents](https://arxiv.org/abs/2509.20175) paper
- Built with [OpenWebUI](https://github.com/open-webui/open-webui)
- Search powered by [Elasticsearch](https://www.elastic.co/)
- LLM integration via [LiteLLM](https://github.com/BerriAI/litellm)
