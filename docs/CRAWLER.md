# Crawler

## Basic Usage

```bash
harmony-crawl \
  --crawler.start_urls+ https://example.com/en https://example.com/fr \
  --crawler.output crawled_data \
  --crawler.max_depth 100 \
  --crawler.delay 1.0 \
  --crawler.concurrent 5
```

**Common options:**
- `--crawler.start_urls+` - URLs to start crawling from (required, use `+` to append multiple)
- `--crawler.allowed_domains+` - Additional domains to allow
- `--crawler.output` - Output directory (default: `output`)
- `--crawler.max_depth` - Maximum crawl depth (default: 100)
- `--crawler.delay` - Delay between requests in seconds (default: 1.0)
- `--crawler.concurrent` - Max concurrent requests (default: 5)
- `--crawler.verbose` - Verbosity level (0-3, default: 0)
- `--print-config` - Print full resolved configuration and exit
- `--help` - Show all available options

**Safety options:**
- `--crawler.safe_mode` - Extra strict safety checks (blocks URLs with id= + action words)
- `--crawler.dry_run` - Test mode without making actual requests
- `--crawler.allow_mutations` - Reduce safety restrictions (use with caution)
- `--crawler.ignore_robots` - Disable robots.txt respect (not recommended)

## Config File

Create a `harmony_config.yaml` file to configure domain routing and spider settings:

```yaml
start_urls:
  - "https://docs.example.com"
  - "https://admin.example.com"

proxy:
  url: http://proxy.example.com:8080  # scheme determines type
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

```bash
harmony-crawl --config harmony_config.yaml --output output/
```

**Proxy support:**
- HTTP/HTTPS: use `http://` or `https://` scheme
- SOCKS4/SOCKS5: use `socks4://` or `socks5://` scheme
- Optional `username` and `password` fields for all types

## Authentication

See [AUTHENTICATION.md](AUTHENTICATION.md) for full docs.

**Quick setup (static cookies):**
```bash
# .env
CERN_COOKIE=your_cookie_value_here
```

**Supported methods:** static cookies, HTTP Basic Auth, Bearer tokens, OAuth2 Client Credentials, Interactive SSO (Playwright, supports 2FA/SAML)

**Example config:**
```yaml
crawler:
  auth:
    providers:
      - type: basic
        domains: ["api\\.example\\.com"]
        username: "user"
        password: "pass"

      - type: playwright_sso
        name: "company-sso"
        domains: ["sso\\.company\\.com"]
        login_url: "https://sso.company.com/login"
```

**Manage sessions:**
```bash
harmony-auth login   # Interactive SSO login
harmony-auth status  # View provider and session status
harmony-auth clear   # Clear all sessions
```

## Safety

The crawler blocks destructive actions at multiple layers (defense-in-depth).

### Mechanisms

1. **HTTP method restriction** — only GET and HEAD by default; POST/PUT/DELETE/PATCH blocked
2. **Dangerous URL patterns** — blocks `/delete/`, `/remove/`, `/destroy/`, `/purge/`, `/edit/`, `/update/`, `/modify/`, `/change/`, `/submit`, `/cancel`, `/logout`, `/signout`, `/admin/.*/delete`, `/admin/.*/edit`
3. **Query parameter filtering** — blocks `action=delete`, `method=POST`, `confirm=yes`, `submit=yes`, `cancel=yes`
4. **Safe mode** (`--crawler.safe_mode`) — also blocks URLs with `id=` + action words, e.g. `https://site.com/edit?id=123`
5. **Dry run** (`--crawler.dry_run`) — logs URLs without making requests
6. **LinkExtractor deny patterns** — early filtering before requests are made

### Best Practices

1. Test new sites with dry-run first:
   ```bash
   harmony-crawl --config config.yaml --crawler.dry_run
   ```

2. Review blocked URLs in logs:
   ```
   [SAFETY BLOCK] https://example.com/admin/delete/123
     Reason: Matched dangerous pattern: /delete/
     Method: GET
     Referer: https://example.com/admin/users
   ```

3. Use safe mode for unknown or admin sites:
   ```bash
   harmony-crawl --config config.yaml --crawler.safe_mode
   ```

4. Only disable safety when absolutely necessary:
   ```bash
   harmony-crawl --config config.yaml --crawler.allow_mutations
   ```

5. Monitor `[SAFETY STATS]` in crawler logs after each run.

6. Limit scope with `allowed_domains`:
   ```yaml
   allowed_domains:
     - docs.example.com
     - help.example.com
   ```

### Interactive Safety Mode

```bash
harmony-crawl --config config.yaml --crawler.interactive_safety true
```

When a URL is blocked, you're prompted:
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

**Via config:**
```yaml
crawler:
  safety_allow_list:
    - "example\\.com/special/edit.*"
    - "docs\\.example\\.com/.*"
  safety_deny_list:
    - "/private/.*"
    - ".*\\?debug=.*"
```

**Via CLI:**
```bash
harmony-crawl --config config.yaml \
  --crawler.safety_allow_list+ "example\\.com/admin/view.*" \
  --crawler.safety_deny_list+ "/sensitive/.*"
```

**`.harmony-safety-lists.json` format:**
```json
{
  "allow_patterns": ["example\\.com/admin/view/\\d+"],
  "deny_patterns": ["/private/.*"],
  "metadata": {"last_updated": "2026-01-08T12:34:56"}
}
```

### Programmatic Safety Config

```python
from harmony.crawler.safety import SafetyConfig

custom_safety = SafetyConfig(
    additional_deny_patterns=[r"/admin/.*", r"/private/.*"],
    allow_list_patterns=[r"example\.com/admin/view/.*"],
    safe_mode=True,
)
```

## Stateful Crawling

Stateful mode tracks change detection and deletion across crawls to avoid redundant downloads and keep the search index accurate.

### Two ES Indices

| Index | Purpose | Managed by |
|-------|---------|------------|
| `harmony` | Searchable content for LLM queries | `harmony-index` |
| `harmony-crawl-state` | Crawl metadata (hashes, ETags, missing counts) | `harmony-crawl` |

### Stateless vs Stateful

**Stateless (default):** no ES required, always downloads all content. Good for one-off crawls.

**Stateful** (enabled with `--crawler.es_state_host`): HTTP-based change detection (If-Modified-Since, ETag), SHA256 hash comparison, deletion tracking with grace period, age-based re-crawling.

### Basic Workflow

```bash
# Initial crawl
harmony-crawl \
  --config harmony_config.yaml \
  --crawler.es_state_host http://localhost:9200

# Re-crawl — skips unchanged content automatically
harmony-crawl \
  --config harmony_config.yaml \
  --crawler.es_state_host http://localhost:9200

# Index with deletion sync
harmony-index \
  --data-dir output \
  --es-host http://localhost:9200 \
  --index-name harmony \
  --sync-deletions \
  --missing-threshold 3
```

### Change Detection Flow

1. Crawler requests URL with `If-Modified-Since` and `If-None-Match` headers
2. `304 Not Modified` → skip download, update `last_seen_at`
3. `200 OK` → download, compute SHA256
   - Hash matches → skip file write, update `last_seen_at`
   - Hash differs → write file, update state and content index
4. `404`/`410` → increment `missing_count` in state

### Deletion Sync Flow

1. Each `404`/`410` increments `missing_count` in state index
2. After threshold (default 3), URL is marked for deletion
3. `harmony-index --sync-deletions` queries state for `missing_count >= threshold` and removes those URLs from the content index

### Advanced Options

**Pause and resume:**
```bash
harmony-crawl --config config.yaml --crawler.jobdir .crawl-state
# Ctrl+C to pause, same command to resume
```

**Age-based re-crawling:**
```bash
harmony-crawl \
  --config config.yaml \
  --crawler.es_state_host http://localhost:9200 \
  --crawler.recrawl_mode age-based \
  --crawler.max_age_days 7
```

**Auto-delete missing URLs:**
```bash
harmony-crawl \
  --config config.yaml \
  --crawler.es_state_host http://localhost:9200 \
  --crawler.delete_missing true \
  --crawler.missing_threshold 3
```

**Full stateful config:**
```yaml
crawler:
  start_urls:
    - "https://docs.example.com"
  es_state_host: http://localhost:9200
  es_state_index: harmony-crawl-state
  jobdir: .crawl-state
  recrawl_mode: full  # or "age-based"
  max_age_days: 7
  delete_missing: false
  missing_threshold: 3
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

**Safety filters:**
- Delete/remove/destroy: `/delete/`, `/remove/`, `/destroy/`
- Edit/update/modify: `/edit/`, `/update/`, `/modify/`
- Form submissions: `/submit`, `?submit=`, `?action=delete`
- Auth URLs: `/logout`, `/signout`, `/sign-out`
- Admin mutations: `/admin/.*/delete`, `/admin/.*/edit`
- API mutations: `/api/.*/delete`, `/api/.*/update`

**Technical filters:**
- JavaScript URLs (`javascript:`)
- Known auth domains (`auth.cern.ch`)

Filtering runs at both LinkExtractor level (early) and SafetyMiddleware level (defense in depth).
