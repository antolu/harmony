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

### 6. MCP Server Integration

Harmony supports the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), allowing you to extend the LLM's capabilities with external tools from MCP servers.

#### What is MCP?

MCP (Model Context Protocol) is an open protocol that standardizes how applications provide context to LLMs. MCP servers expose tools, resources, and prompts that can be dynamically integrated into LLM applications.

#### Built-in Tools

Harmony includes these built-in tools:
- `search_documents` - Search the Elasticsearch knowledge base
- `get_document_details` - Get full content of a specific document
- `fetch_url` - Fetch and parse web pages at runtime
- `fetch_pdf` - Download and extract text from PDFs
- `fetch_document` - Universal document parser (DOCX, XLSX, ODT, TXT, CSV)

#### Configuring MCP Servers

Add MCP server configurations to your `.env` file:

```bash
# Example: Add filesystem access and GitHub integration
MCP_SERVERS='[
  {
    "name": "filesystem",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/directory"],
    "env": {}
  },
  {
    "name": "github",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": {
      "GITHUB_PERSONAL_ACCESS_TOKEN": "your_github_token_here"
    }
  }
]'
```

**Configuration Fields:**
- `name` - Friendly name for the MCP server
- `command` - Executable to run (e.g., `npx`, `python`, `node`)
- `args` - Command-line arguments as array
- `env` - Environment variables for the MCP server process

#### Available MCP Servers

Popular MCP servers you can integrate:

**Official Servers:**
- `@modelcontextprotocol/server-filesystem` - Local file system access
- `@modelcontextprotocol/server-github` - GitHub API integration
- `@modelcontextprotocol/server-slack` - Slack workspace integration
- `@modelcontextprotocol/server-postgres` - PostgreSQL database queries
- `@modelcontextprotocol/server-sqlite` - SQLite database queries
- `@modelcontextprotocol/server-memory` - Persistent key-value storage

**Community Servers:**
- Browse more at [https://github.com/modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)

#### Example: Adding Filesystem Access

```bash
# In .env
MCP_SERVERS='[
  {
    "name": "filesystem",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/you/Documents"],
    "env": {}
  }
]'
```

Now when you query the LLM, it can read files from `/Users/you/Documents`:
- "What files are in my Documents folder?"
- "Read the contents of report.txt"
- "Search for Python files in my Documents"

#### Example: Adding GitHub Integration

```bash
# In .env
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here

MCP_SERVERS='[
  {
    "name": "github",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": {
      "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"
    }
  }
]'
```

Now the LLM can interact with GitHub:
- "Show me recent issues in owner/repo"
- "Create an issue in my repository"
- "Search for pull requests about authentication"

#### Verifying MCP Tools

Check which tools are available:

```bash
# API startup logs will show registered tools
docker compose logs harmony-api | grep "Registered.*tools"

# Example output:
# Registered 5 built-in tools: ['search_documents', 'get_document_details', 'fetch_url', 'fetch_pdf', 'fetch_document']
# Registered 3 MCP tools. Total tools: 8
```

#### Document Cache

To reduce latency and external API calls, Harmony caches fetched documents:

```bash
# In .env (default values shown)
DOCUMENT_CACHE_ENABLED=true
DOCUMENT_CACHE_TTL=3600        # 1 hour
DOCUMENT_CACHE_MAX_SIZE=1000   # Max cached documents
```

Cached content includes:
- URLs fetched with `fetch_url`
- PDFs downloaded with `fetch_pdf`
- Documents parsed with `fetch_document`

Cache stats are logged periodically for monitoring.

#### Security Considerations

⚠️ **Important:** MCP servers run with the permissions of the Harmony API process.

- **Filesystem server:** Only grant access to necessary directories
- **GitHub server:** Use tokens with minimal required scopes
- **Database servers:** Use read-only credentials when possible
- **Custom servers:** Audit third-party MCP servers before use

#### Troubleshooting

**MCP tools not appearing:**
1. Check API logs: `docker compose logs harmony-api`
2. Verify JSON syntax in `MCP_SERVERS` environment variable
3. Ensure MCP server command is available (e.g., `npx` installed)
4. Check MCP server logs for initialization errors

**MCP server connection errors:**
- Verify environment variables are set correctly
- Check file paths and permissions for filesystem server
- Validate API tokens for external services
- Ensure MCP server version is compatible (mcp >= 1.1.0)

#### Creating Custom MCP Servers

You can create your own MCP servers to extend Harmony with custom tools:

1. Follow the [MCP Python SDK documentation](https://github.com/modelcontextprotocol/python-sdk)
2. Implement your tools using the `@server.call_tool()` decorator
3. Add your server to `MCP_SERVERS` configuration
4. Harmony will automatically discover and register your tools

Example Python MCP server:

```python
from mcp.server import Server, Tool
from mcp.server.stdio import stdio_server

server = Server("my-custom-server")

@server.call_tool()
async def my_custom_tool(argument: str) -> str:
    """My custom tool description."""
    # Your tool logic here
    return f"Result: {argument}"

if __name__ == "__main__":
    stdio_server(server)
```

Then configure in `.env`:

```bash
MCP_SERVERS='[
  {
    "name": "custom",
    "command": "python",
    "args": ["path/to/my_server.py"],
    "env": {}
  }
]'
```

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
