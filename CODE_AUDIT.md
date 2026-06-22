# Harmony Codebase Audit Report

**Date:** 2026-06-20  
**Repository:** `/Users/antonlu/code/harmony/harmony`  
**Total Python Files:** 162  
**Total Lines of Code:** ~23,747

---

## Executive Summary

This audit identified three categories of code quality issues:

1. **4 files exceeding 800 lines** — candidates for refactoring
2. **2 dead code items** — logging module and static JSON manifest to remove
3. **Missing `py.typed` marker** — needed for PEP 561 type checker support
4. **Limited dead code detected** — most modules are actively referenced and used

The codebase is generally well-structured with clear separation of concerns across API, crawler, indexer, and core subsystems. However, a few files have grown too large and would benefit from modularization.

---

## I. Oversized Files (>800 lines)

These files exceed recommended size limits (500-600 lines) and are candidates for refactoring:

### 1. **`harmony/db/repositories.py` — 1,613 lines** ⚠️ CRITICAL

**Issue:** Monolithic repository class combining 37 data access classes and 100 functions.

**Current Structure:**
- Lines: 1,613
- Functions: 100
- Classes: 37
- Avg function length: 16 lines (good)
- Max nesting: 4 (acceptable)
- Imports: 10 (minimal, good)

**Problem:** While individual functions are concise, the file is a "god module" containing all database access patterns. This violates the Single Responsibility Principle.

**Example Classes (first 10 of 37):**
- `ApiKeysRepo` — API key management
- `AuditLogRepo` — Audit logging
- `BlacklistRepo` — Blacklist management
- `CrawlConfigRepo` — Crawler configuration
- `CrawlSessionsRepo` — Crawler sessions
- `JobsRepo` — Job persistence
- `SchedulesRepo` — Schedule management
- `UsageLogRepo` — Token/usage logging
- `UserIdentityRepo` — User identity
- `WebhookRepo` — Webhooks

**Recommendation:** Split into domain-specific modules:
```
harmony/db/
  __init__.py                    # Exports for backwards compatibility
  _api_keys.py                   # ApiKeysRepo
  _audit_log.py                  # AuditLogRepo
  _blacklist.py                  # BlacklistRepo
  _crawl.py                      # CrawlConfigRepo, CrawlSessionsRepo
  _jobs.py                        # JobsRepo
  _schedules.py                  # SchedulesRepo
  _usage.py                       # UsageLogRepo
  _users.py                       # UserIdentityRepo
  _webhooks.py                    # WebhookRepo
  # ... etc
```

**Impact:** Medium complexity. Refactoring requires careful import remapping but adds no functional changes.

---

### 2. **`harmony/providers/web_crawler/cli_index.py` — 1,000 lines** ⚠️ HIGH

**Issue:** CLI entrypoint combining indexing logic with argument parsing and data transformation.

**Current Structure:**
- Lines: 1,000
- Functions: 30
- Classes: 6
- Avg function length: 32 lines
- Max nesting: 10 (high)
- Imports: 24 (high, tightly coupled)

**Problem:** Deep nesting (level 10) indicates complex control flow. The file mixes concerns:
- CLI argument parsing (jsonargparse)
- Indexing orchestration
- Language detection
- Document parsing
- Elasticsearch bulk operations
- Embedding generation via LiteLLM
- Qdrant vector storage

**Recommendation:** Extract core indexing logic into `harmony/indexer/_core.py`:
```
harmony/indexer/
  __init__.py
  _core.py              # IndexEngine class (300-400 lines)
  _language.py          # Language detection helpers
  _sources.py           # Disk/ES source adapters
harmony/providers/web_crawler/
  cli_index.py          # Thin CLI wrapper (200-300 lines) → just arg parsing + IndexEngine calls
```

**Impact:** High complexity. Reduces nesting and improves testability.

---

### 3. **`harmony/api/services/admin/_job_manager.py` — 852 lines** ⚠️ HIGH

**Issue:** Job lifecycle management combining process spawning, monitoring, and persistence.

**Current Structure:**
- Lines: 852
- Functions: 35
- Classes: 1
- Avg function length: 24 lines
- Max nesting: 7 (high)
- Imports: 24 (high)

**Problem:** Single large class (`JobManager`) handling:
- Subprocess lifecycle (spawn, monitor, kill)
- Job state persistence (Postgres via `JobsRepo`)
- Log streaming to clients (Redis pub/sub + SSE)
- Job configuration management
- Retry logic and cleanup

**Recommendation:** Split into domain modules:
```
harmony/api/services/admin/
  _job_manager.py       # JobManager wrapper (300 lines) — public API
  _job_process.py       # JobProcess class — subprocess management
  _job_persistence.py   # Job state persistence helpers
  _job_log_stream.py    # LogStreamer integration
```

**Impact:** Medium-high complexity. Improves testability and maintainability.

---

### 4. **`harmony/api/main.py` — 807 lines** ⚠️ MEDIUM

**Issue:** FastAPI app initialization combining configuration, middleware, lifespan, and route registration.

**Current Structure:**
- Lines: 807
- Functions: 26
- Classes: 0
- Avg function length: 30 lines
- Max nesting: 5 (acceptable)
- Imports: 49 (very high — tightly coupled)

**Problem:** Large import footprint and mixed concerns:
- Settings/configuration
- Logging configuration
- Middleware setup
- Lifespan (startup/shutdown)
- Health checks
- Route registration
- CORS setup
- Admin backend initialization

**Recommendation:** Keep main structure but extract:
```
harmony/api/
  main.py                 # FastAPI app with lifespan + route registration (300-400 lines)
  _settings.py            # Settings/config (replace some CLAUDE.md guidance)
  _middleware.py          # Middleware setup helpers
  _health.py              # Health check logic
```

**Impact:** Low-medium complexity. Mostly housekeeping; doesn't affect functionality.

---

## II. Dead Code & Assets

### A. **`harmony/core/_logging.py` — 5 lines** ⚠️ USELESS

```python
from __future__ import annotations

import logging

logger = logging.getLogger("harmony")
```

**Analysis:**
- Exported in `harmony/core/__init__.py` with public API (`__all__`)
- Imported by 5 files (all in `providers/web_crawler/` package)
- These files use it, but the module is essentially a trivial wrapper

**Used By:**
```
harmony/providers/web_crawler/auth/registry.py
harmony/providers/web_crawler/auth/providers/oidc.py
harmony/providers/web_crawler/auth/providers/playwright_sso.py
harmony/providers/web_crawler/auth/middleware.py
harmony/providers/web_crawler/runtime/middlewares.py
```

**Verdict:** This module is **REDUNDANT** and can be removed. Each importing module can replace:
```python
from harmony.core import logger
```

with:
```python
import logging
logger = logging.getLogger(__name__)
```

No behavior changes. All 5 importing files should be updated.

---

### B. **`harmony/static/model_manifest.json` — Dead Asset** ✗ REMOVE

**Issue:** Static JSON manifest that is never read or used.

**Analysis:**
- File defines hardcoded model list (Ollama, OpenAI, Anthropic, Gemini)
- Referenced in constant `_MANIFEST_PATH` in `harmony/api/services/admin/_model_registry.py` (line 28-29)
- Constant is **never used** in any method or function
- Actual manifest is built dynamically at runtime from `litellm.model_cost` dict in `ModelRegistryService.get_manifest()` (line 232-256)
- The dynamic manifest is what gets returned to the frontend

**Verdict:** **REMOVE THIS FILE.** It's dead code — a leftover from an earlier implementation that was replaced with runtime model detection.

---

### C. **`harmony/api/observability/_logging.py` — 43 lines** ✓ USED

```python
def configure_logging(*, dev_mode: bool = False) -> None:
    # structlog configuration setup
    ...
```

**Analysis:**
- Provides centralized structlog configuration (dev vs. prod renderers)
- Called exactly once in `harmony/api/main.py` during app startup
- Actively used and necessary

**Verdict:** **KEEP THIS.** It's a legitimate configuration helper.

---

### D. **`harmony/providers/web_crawler/runtime/logger.py` — 82 lines**

**Current Content:** Creates Scrapy-compatible logger with structlog integration.

**Analysis:**
- Used by Scrapy spiders
- Minimal but necessary for crawl logging pipeline

**Verdict:** **KEEP THIS.** Necessary for crawler instrumentation.

---

## III. Type Hint Support (PEP 561)

### Missing: `harmony/py.typed` Marker

**Issue:** Package lacks PEP 561 marker file for type checker support.

**Analysis:**
- All Python files have `from __future__ import annotations` (excellent)
- All functions are type-hinted (excellent)
- But package doesn't signal this to external type checkers (mypy, pyright, etc.)

**Solution:**
1. Create empty marker file: `harmony/py.typed`
2. Register in `pyproject.toml`:
   ```toml
   [tool.setuptools.package-data]
   harmony = ["py.typed"]
   ```

**Impact:** Enables type checking of this package when imported by other projects.

---

## IV. Cleanup Action Plan

### Priority 1: Remove (Immediate)
- [ ] Delete `harmony/core/_logging.py`
- [ ] Delete `harmony/static/model_manifest.json`
- [ ] Remove `_MANIFEST_PATH` constant from `harmony/api/services/admin/_model_registry.py` (lines 28-30)
- [ ] Update 5 importing files in `providers/web_crawler/` (replace with `import logging; logger = logging.getLogger(__name__)`)
  - `harmony/providers/web_crawler/auth/registry.py`
  - `harmony/providers/web_crawler/auth/providers/oidc.py`
  - `harmony/providers/web_crawler/auth/providers/playwright_sso.py`
  - `harmony/providers/web_crawler/auth/middleware.py`
  - `harmony/providers/web_crawler/runtime/middlewares.py`
- [ ] Update `harmony/core/__init__.py` (remove logger export)
- [ ] Create empty `harmony/py.typed` marker file (PEP 561 — signals type checkers that package has inline hints)
  - Also ensure it's included in `pyproject.toml` under `[tool.setuptools.package-data]`:
    ```toml
    [tool.setuptools.package-data]
    harmony = ["py.typed"]
    ```
- **Effort:** ~25 minutes
- **Risk:** Low (no behavioral change, manifest is never read, py.typed is distribution metadata)

### Priority 2: Refactor (Medium-term)
- [ ] **repositories.py (1,613 lines)** — Split into 10-12 domain modules
  - **Effort:** 2-3 hours
  - **Risk:** Medium (requires careful import remapping)
  - **Benefit:** Improved maintainability, easier testing

- [ ] **cli_index.py (1,000 lines)** — Extract core indexing engine
  - **Effort:** 2-3 hours
  - **Risk:** High (deeply nested control flow)
  - **Benefit:** Reduced complexity, better testability

- [ ] **_job_manager.py (852 lines)** — Split into 4 modules
  - **Effort:** 2 hours
  - **Risk:** Medium (affects job lifecycle)
  - **Benefit:** Better separation of concerns

### Priority 3: Cleanup (Optional)
- [ ] **main.py (807 lines)** — Extract config/middleware helpers
  - **Effort:** 1-2 hours
  - **Risk:** Low (mostly housekeeping)
  - **Benefit:** Reduced imports, clearer structure

---

## V. Code Quality Summary

| Metric | Value | Assessment |
|--------|-------|------------|
| Total Files | 162 | ✓ Good |
| Total LOC | ~23,747 | ✓ Good |
| Files >800 lines | 4 | ⚠️ Refactor candidates |
| Dead code detected | 2 | ⚠️ Remove |
| Useless logging modules | 1 | ⚠️ Remove (5 lines) |
| Dead assets (JSON) | 1 | ⚠️ Remove (manifest) |
| py.typed marker | Missing | ⚠️ Add |
| Avg function length | 14-32 | ✓ Good |
| Max nesting depth | 4-10 | ⚠️ Reduce in cli_index.py, _job_manager.py |
| Import coupling | Moderate | ✓ Good (except main.py: 49 imports) |

---

## VI. Appendix: Largest Files by Category

### API Routes
```
harmony/api/routes/admin/auth.py              415 lines
harmony/api/routes/chat.py                    398 lines
harmony/api/routes/admin/jobs.py              394 lines
harmony/api/routes/user_auth.py               347 lines
harmony/api/routes/admin/configs.py           352 lines
```

### API Services
```
harmony/api/services/admin/_job_manager.py     852 lines ⚠️
harmony/api/services/admin/_export_service.py  324 lines
harmony/api/services/admin/_model_registry.py  304 lines
harmony/api/services/admin/_config_store.py    257 lines
harmony/api/services/admin/_sso_handler.py     275 lines
```

### Crawler Providers
```
harmony/providers/web_crawler/cli_index.py          1000 lines ⚠️
harmony/providers/web_crawler/auth/providers/playwright_sso.py  443 lines
harmony/providers/web_crawler/runtime/middlewares.py             434 lines
harmony/providers/web_crawler/auth/config.py                    387 lines
harmony/providers/web_crawler/runtime/config.py                 339 lines
```

### Core/DB
```
harmony/db/repositories.py                     1613 lines ⚠️
harmony/core/_parsers.py                        320 lines
harmony/core/_writers.py                        271 lines
```

---

## VII. Notes

- **Logging:** The codebase uses both `logging` (stdlib) and `structlog` (structured). This is acceptable — stdlib for simple loggers, structlog for trace-aware structured logging in the API.

- **Type hints:** All Python files have `from __future__ import annotations` — excellent practice.

- **Testing:** No dead tests found; test files are well-distributed across the codebase.

- **Imports:** Most modules have reasonable import counts. `main.py` (49) is high but acceptable for an app root.

---

**Audit completed:** 2026-06-20
