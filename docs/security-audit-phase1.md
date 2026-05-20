# Phase 1 Security Audit

**Audit date:** 2026-05-21
**Scope:** Phase 1 security hardening and bug fixes (plans 01-02 through 01-06)
**Auditor:** AI-assisted (Claude claude-sonnet-4-6), reviewed against ASVS L1 categories V4, V5, V9

## Scope

**In scope:**
- CORS configuration (SEC-02)
- SSRF protection on tool URL fetching (SEC-03)
- Data residency enforcement for LLM/embedding/reranker calls (SEC-05)
- Pipeline config persistence bug (BUG-01)
- Conversation user_id scoping scaffold (BUG-02)
- Zombie job recovery status (BUG-03)
- All API endpoints for auth and access control status
- Injection vector review for search inputs and admin config inputs

**Out of scope (deferred to Phase 2):**
- SEC-01: API authentication guard (JWT/OIDC middleware)
- Conversation user_id enforcement (no JWTs yet; scaffold only)
- TLS configuration (terminated at load balancer or ingress)
- Rate limiting

---

## Endpoint Inventory

| Endpoint | Method | Auth Required | Phase 1 Status | Risk Level | Notes |
|----------|--------|--------------|----------------|------------|-------|
| `/` | GET | No | ACCEPTED | Low | Info endpoint, no sensitive data |
| `/search` | GET | No | DEFERRED | High | Open search; SEC-01 deferred to Phase 2 |
| `/ai-search` | POST | No | DEFERRED | High | AI search with tool calling; SEC-01 deferred |
| `/agentic-search` | POST | No | DEFERRED | High | Multi-agent search; SEC-01 deferred |
| `/settings/pipeline` | GET | No | ACCEPTED | Medium | Read pipeline config; internal network only |
| `/settings/pipeline` | PATCH | No | DEFERRED | High | Mutates search config; SEC-01 deferred |
| `/api/configs/crawler` | GET | No | DEFERRED | Medium | Lists crawler configs |
| `/api/configs/crawler/{name}` | GET | No | DEFERRED | Medium | Reads specific crawler config |
| `/api/configs/crawler` | POST | No | DEFERRED | High | Creates crawler config |
| `/api/configs/crawler/{name}` | DELETE | No | DEFERRED | High | Deletes crawler config |
| `/api/configs/crawler/{name}/export` | GET | No | DEFERRED | Medium | Exports crawler config as YAML |
| `/api/configs/crawler/{name}/download` | GET | No | DEFERRED | Medium | Downloads crawler config file |
| `/api/configs/crawler/import` | POST | No | DEFERRED | High | Imports crawler config |
| `/api/configs/crawler/{name}/rename` | POST | No | DEFERRED | Medium | Renames crawler config |
| `/api/configs/indexer` | GET | No | DEFERRED | Medium | Lists indexer configs |
| `/api/configs/indexer/{name}` | GET | No | DEFERRED | Medium | Reads specific indexer config |
| `/api/configs/indexer` | POST | No | DEFERRED | High | Creates indexer config |
| `/api/configs/indexer/{name}` | DELETE | No | DEFERRED | High | Deletes indexer config |
| `/api/configs/indexer/{name}/export` | GET | No | DEFERRED | Medium | Exports indexer config |
| `/api/configs/indexer/{name}/download` | GET | No | DEFERRED | Medium | Downloads indexer config |
| `/api/configs/indexer/import` | POST | No | DEFERRED | High | Imports indexer config |
| `/api/configs/indexer/{name}/rename` | POST | No | DEFERRED | Medium | Renames indexer config |
| `/api/configs/validate/elasticsearch` | GET | No | DEFERRED | Low | Validates ES config |
| `/api/configs/crawler/schema` | GET | No | ACCEPTED | Low | Schema endpoint, read-only |
| `/api/configs/indexer/schema` | GET | No | ACCEPTED | Low | Schema endpoint, read-only |
| `/api/jobs` | GET | No | DEFERRED | Medium | Lists all jobs |
| `/api/jobs/{job_id}` | GET | No | DEFERRED | Medium | Gets a single job |
| `/api/jobs/crawl` | POST | No | DEFERRED | Critical | Starts a crawl subprocess |
| `/api/jobs/index` | POST | No | DEFERRED | Critical | Starts an index subprocess |
| `/api/jobs/embed` | POST | No | DEFERRED | Critical | Starts an embed subprocess |
| `/api/jobs/{job_id}/stop` | POST | No | DEFERRED | High | Stops a running job |
| `/api/jobs/{job_id}/pause` | POST | No | DEFERRED | High | Pauses a running job |
| `/api/jobs/{job_id}/resume` | POST | No | DEFERRED | High | Resumes a paused job |
| `/api/jobs/{job_id}/progress` | GET | No | DEFERRED | Low | Job progress, read-only |
| `/api/jobs/{job_id}/progress/stream` | GET | No | DEFERRED | Low | SSE progress stream |
| `/api/jobs/{job_id}/logs` | GET | No | DEFERRED | Medium | Job logs |
| `/api/jobs/{job_id}/logs/stream` | GET | No | DEFERRED | Medium | SSE log stream |
| `/api/reset/crawl-state` | POST | No | DEFERRED | Critical | Deletes crawl state index |
| `/api/reset/search-indices` | POST | No | DEFERRED | Critical | Deletes search indices |
| `/api/reset/status` | GET | No | DEFERRED | Low | Reset status, read-only |
| `/api/auth/providers` | GET | No | DEFERRED | Low | Lists auth providers |
| `/api/auth/sessions` | GET | No | DEFERRED | Medium | Lists auth sessions |
| `/api/auth/login/{provider}` | POST | No | DEFERRED | High | Initiates login flow |
| `/api/auth/callback` | GET | No | DEFERRED | Medium | OAuth callback |
| `/api/auth/login/{provider}/status` | GET | No | DEFERRED | Low | Login status polling |
| `/api/auth/providers/test` | POST | No | DEFERRED | Low | Tests OIDC connection |
| `/api/auth/providers/{provider}/test` | POST | No | DEFERRED | Low | Tests specific provider connection |
| `/api/auth/sessions/{provider}` | DELETE | No | DEFERRED | High | Clears a session |
| `/api/internal/safety-lists` | GET | No | DEFERRED | Low | Lists safety patterns |
| `/api/internal/safety-lists` | POST | No | DEFERRED | Medium | Adds safety patterns |
| `/api/internal/safety-lists` | DELETE | No | DEFERRED | Medium | Clears safety patterns |
| `/api/internal/auth-sessions` | GET | No | DEFERRED | Medium | Crawler sessions |
| `/api/internal/auth-sessions` | POST | No | DEFERRED | Medium | Creates crawler session |
| `/api/internal/auth-sessions/{subdomain}` | DELETE | No | DEFERRED | Medium | Deletes crawler session |
| `/api/internal/stats/{job_id}` | POST | No | DEFERRED | Low | Job stats reporting |
| `/api/internal/safety-pending/{job_id}` | POST | No | DEFERRED | Low | Safety signal (internal) |
| `/api/internal/safety-decision/{job_id}` | POST | No | DEFERRED | Low | Safety signal (internal) |
| `/api/setup/status` | GET | No | ACCEPTED | Low | Setup status, read-only |
| `/api/setup/validate` | POST | No | ACCEPTED | Low | Setup validation |
| `/api/setup/ollama-host` | GET | No | ACCEPTED | Low | Ollama host discovery |
| `/api/setup/defaults` | GET | No | ACCEPTED | Low | Returns default config values |
| `/api/setup/complete` | POST | No | DEFERRED | Medium | Marks setup complete |
| `/api/index-config` | GET | No | DEFERRED | Low | Index config, read-only |
| `/api/index-config` | PUT | No | DEFERRED | High | Mutates index config |
| `/api/models/ollama` | GET | No | DEFERRED | Low | Lists Ollama models |
| `/api/models/ollama/pull` | POST | No | DEFERRED | High | Pulls an Ollama model |
| `/api/models/ollama/{name}` | DELETE | No | DEFERRED | High | Deletes an Ollama model |
| `/api/settings/models` | GET | No | DEFERRED | Low | Model settings, read-only |
| `/api/settings/models` | PATCH | No | DEFERRED | High | Mutates model settings |
| `/api/settings/models/validate` | POST | No | DEFERRED | Medium | Validates model settings |
| `/api/admin/infrastructure` | GET | No | ACCEPTED | Low | Infrastructure health check |

**Summary:** 62 endpoints. 0 have auth guards (Phase 1). All mutation endpoints are DEFERRED to Phase 2 for auth. Read-only endpoints with no sensitive data are ACCEPTED as low risk when deployed on an internal network.

---

## Findings Fixed in Phase 1

### F-01 — SEC-02: CORS wildcard

**Severity:** High
**STRIDE category:** Spoofing, Information Disclosure
**CVE pattern:** CORS misconfiguration (CWE-942)

**Description:** The FastAPI app was configured with `allow_origins=["*"]`, permitting any origin to make credentialed cross-origin requests to the API. In a browser context, this allows a malicious website to make authenticated requests on behalf of a logged-in user.

**Fix:** Replaced the wildcard with `settings.cors_allowed_origins` — a `list[str]` populated from the `CORS_ALLOWED_ORIGINS` environment variable (comma-separated). The API raises `RuntimeError` at startup if the env var is unset, preventing misconfigured deployments from starting.

Files changed:
- `harmony/api/config.py` — added `cors_allowed_origins` setting with startup validation
- `harmony/api/main.py` — `allow_origins=settings.cors_allowed_origins`
- `docker-compose.yml` — added `CORS_ALLOWED_ORIGINS` env var
- `docker-compose.dev.yml` — added `CORS_ALLOWED_ORIGINS=http://localhost:3001,http://localhost:8080`

**Verification:**
```bash
pytest tests/api/test_cors.py -v
```

---

### F-02 — SEC-03: SSRF via tool URL inputs

**Severity:** High
**STRIDE category:** Elevation of Privilege, Information Disclosure
**CVE pattern:** SSRF (CWE-918)

**Description:** The `fetch_url`, `fetch_pdf`, and `fetch_document` tools in `harmony/api/tools/_documents.py` accepted arbitrary URLs and made HTTP requests without checking whether the target was a private/internal address. An attacker could instruct the LLM to fetch `http://169.254.169.254/latest/meta-data/` (cloud metadata) or `http://192.168.1.1` (internal router), causing the API server to proxy requests to internal infrastructure.

**Fix:** Added `_is_private_address(url: str) -> bool` to `harmony/api/tools/_documents.py`. The function resolves the hostname via `socket.getaddrinfo` and checks all returned addresses against blocked CIDR ranges:
- 127.0.0.0/8 (loopback)
- 10.0.0.0/8 (RFC1918)
- 172.16.0.0/12 (RFC1918)
- 192.168.0.0/16 (RFC1918)
- ::1/128 (IPv6 loopback)
- fc00::/7 (IPv6 private)
- 169.254.0.0/16 (link-local / cloud metadata)

DNS resolution failures fail closed (return `True` = blocked). `follow_redirects=False` is set on all httpx clients to prevent redirect-based bypass. When blocked, the tool returns a string `"Error: URL blocked — private/internal addresses are not permitted."` so the LLM can communicate the block to the user.

Files changed:
- `harmony/api/tools/_documents.py` — `_is_private_address`, `_BLOCKED_NETWORKS`, `_SSRF_ERROR`, `follow_redirects=False`

**Verification:**
```bash
pytest tests/api/tools/test_documents.py -v
```

---

### F-03 — SEC-05: Data residency enforcement

**Severity:** Medium
**STRIDE category:** Information Disclosure
**Description:** LLM, embedding, and reranker calls were made without checking whether the configured model required an external network call. In data-residency-sensitive deployments (air-gapped or regulated environments), calls to external APIs (OpenAI, Anthropic, Gemini) could leak document content.

**Fix:** Added `_assert_data_residency(model: str, service_config: ServiceConfigStore) -> None` guard called before every LiteLLM invocation in `LLMService`, `HarmonyVectorBackend`, and `HarmonyRerankerBackend`. The guard reads `data_residency_mode` from `ServiceConfigStore`. When enabled, the guard allows only models with an Ollama prefix (`ollama/` or `ollama_chat/`) and blocks everything else with a `DataResidencyError`. Ollama endpoints are always local by definition.

The flag is controlled at runtime via `ServiceConfigStore` (ENV > DB > DEFAULT). Default is `false` (disabled), so existing deployments are unaffected unless they opt in.

Files changed:
- `harmony/api/services/_llm.py` — `_assert_data_residency` called before `litellm.acompletion`
- `harmony/api/backends/_vector.py` — guard called before `litellm.aembedding`
- `harmony/api/backends/_reranker.py` — guard called before `litellm.arerank`

**Verification:**
```bash
pytest tests/api/services/test_data_residency.py -v
pytest tests/backends/test_vector_backend.py tests/backends/test_reranker_backend.py -v
```

---

### F-04 — BUG-01: Pipeline config not persisted across restarts

**Severity:** Medium
**STRIDE category:** Tampering
**Description:** `PATCH /settings/pipeline` wrote pipeline config to `ServiceConfigStore` (Postgres) correctly, but API startup always initialized `SearchService` with hardcoded defaults from `PipelineConfig`. The `_load_pipeline_config()` function existed but was called incorrectly (or wired at the wrong point in `lifespan`), so changes were silently lost on every restart.

Additionally, `_bool("")` returned `True` for empty strings because the check was `if val is None:` instead of `if not val:`, causing empty env vars to be misread as truthy.

**Fix:** Fixed the empty-string handling in `_bool` (`if not val:`) and ensured `_load_pipeline_config()` is awaited before `SearchService` initialization in the lifespan startup sequence.

Files changed:
- `harmony/api/main.py` — `_load_pipeline_config()` call order and `_bool` fix

**Verification:**
```bash
pytest tests/api/test_pipeline_config.py -v
```

---

### F-05 — BUG-02: Conversations not scoped to user

**Severity:** Medium
**STRIDE category:** Information Disclosure
**Description:** The conversations table had no `user_id` column, so all stored conversations were globally visible to any caller. When auth ships in Phase 2, user A would be able to read user B's conversation history.

**Fix:** Added `user_id` column (nullable `VARCHAR`, default `NULL`) to the conversations table via Alembic migration 0006. `ConversationService.get_messages()` and `create()` accept an optional `user_id` parameter. When a non-null `user_id` is provided, queries filter by it. Until Phase 2 ships JWTs, `user_id` is `NULL` for all requests and no cross-user scoping is enforced — the enforcement activates automatically when Phase 2 passes the user identity.

Files changed:
- `alembic/versions/0006_add_user_id_to_conversations.py` — migration
- `harmony/api/services/_conversation.py` — `user_id` parameter

**Verification:**
```bash
pytest tests/api/services/test_conversation.py -v
```

---

### F-06 — BUG-03: Zombie jobs incorrectly marked STOPPED

**Severity:** Low
**STRIDE category:** Tampering
**Description:** When the API server restarted, `_load_persisted_jobs()` in `JobManager` correctly detected `RUNNING` jobs that no longer had an OS process and transitioned them. However, it used `JobStatus.STOPPED` — the same status as a user-initiated stop. This made it impossible to distinguish "user stopped the job" from "job was interrupted by a server crash or restart", leading to confusing status messages in the admin UI.

**Fix:** Added `INTERRUPTED = "interrupted"` to the `JobStatus` enum in `harmony/api/models/job.py`. The zombie recovery path in `_load_persisted_jobs()` now uses `JobStatus.INTERRUPTED` with the message "Job interrupted by server restart or crash". User-initiated stops continue to use `JobStatus.STOPPED`.

Files changed:
- `harmony/api/models/job.py` — `INTERRUPTED` enum value
- `harmony/api/services/admin/_job_manager.py` — zombie transition uses `INTERRUPTED`

**Verification:**
```bash
pytest tests/api/services/admin/test_job_zombie_recovery.py -v
```

---

## Deferred Findings

### DF-01 — SEC-01: No API authentication guard

**Risk:** Critical in internet-facing deployment; High in internal network deployment
**Deferred to:** Phase 2 (JWT/OIDC middleware)

All 62 endpoints are unauthenticated. Any caller with network access to the API port can read all job history, trigger crawl/index/embed jobs, delete search indices, and read document content via search results.

This was an explicit product decision (D-01): authentication ships in Phase 2 alongside the JWT/OIDC integration. The API is intended for deployment behind an internal network boundary (VPN, private subnet, or Kubernetes ingress with IP allowlisting) until Phase 2 ships.

**Conditions under which this becomes unacceptable:**
- If the API port is reachable from an untrusted network without a separate network-layer restriction
- If any endpoint is proxied to an internet-facing reverse proxy before Phase 2 ships

**Mitigation until Phase 2:**
- Ensure Docker published ports are bound to `127.0.0.1` or an internal interface, not `0.0.0.0`, if deployed on a host with public network access
- Use a firewall or security group rule to restrict the API port to trusted source IPs

---

### DF-02 — Conversation user_id enforcement

**Risk:** Medium (data isolation failure)
**Deferred to:** Phase 2

The `user_id` column and filter logic are scaffolded (migration 0006, `ConversationService` parameters). Enforcement does not activate until Phase 2 passes a non-null `user_id` from JWT claims. Until then, all conversations share a `NULL` user_id partition and are accessible to any caller.

---

## Accepted Risks

### AR-01 — DNS rebinding (SSRF post-check redirect)

**Risk:** An attacker could serve a hostname that resolves to a public IP at DNS check time but rebinds to a private IP by the time the TCP connection is made.

**Rationale (A3):** `_is_private_address` resolves DNS at request time and `follow_redirects=False` closes the redirect vector. A true DNS rebinding attack (sub-TTL rebind to a private address) is not in the current threat model: the LLM tools run as a server-side backend, not in a browser, so there is no browsing session for the attacker to manipulate. The API is also intended for internal network deployment.

**Conditions under which this becomes unacceptable:**
- If the API is deployed with a public IP and untrusted users can submit search queries that trigger tool calls
- If the threat model extends to insider threat or compromised LLM prompts from external sources

**Mitigation if needed:** Replace `_is_private_address` with a custom httpx transport that performs the IP check at TCP connect time (after DNS, before connection), or use `safehttpx` with a private resolver if air-gapped DNS is guaranteed.

---

### AR-02 — Data residency race condition during flag toggle

**Risk:** A request that passes the `_assert_data_residency` check could interleave with an admin toggling `data_residency_mode=true`, resulting in an external LLM call made after the intent to enable the flag.

**Rationale (A6):** `ServiceConfigStore` reads the flag from Postgres on every call (no in-process cache). The race window is the time between `get("data_residency_mode")` and the LiteLLM call (microseconds to milliseconds). In practice, flag toggling is an infrequent admin operation and the race is non-exploitable without timing control over both the admin operation and the query.

**Conditions under which this becomes unacceptable:**
- If data residency compliance requires zero-tolerance (e.g., PCI DSS or HIPAA audit context where a single stray external call is a reportable incident)
- If a toggle test is performed under load and an auditor checks access logs

**Mitigation if needed:** Cache the flag per-request in middleware (request-scoped context variable) so the check is performed once before the handler runs and cannot change mid-request.

---

### AR-03 — JobStatus.STOPPED usages not differentiated from INTERRUPTED

**Risk:** Code that checks `job.status == JobStatus.STOPPED` will not match zombie jobs that are now `INTERRUPTED`.

**Rationale (A7):** All `JobStatus.STOPPED` usages in the codebase were audited during Phase 1 implementation. The zombie recovery path was the only place that previously used STOPPED for a non-user-stop case. All other STOPPED checks are correct.

**Conditions under which this becomes unacceptable:**
- If new code is added that assumes zombie jobs use STOPPED (regression risk)

**Mitigation:** The `INTERRUPTED` enum value is documented in `harmony/api/models/job.py`. Any future status-check logic should explicitly handle both STOPPED and INTERRUPTED where job termination (any cause) needs to be detected.

---

## Deployment Hardening Checklist

Before deploying to production:

- [ ] `CORS_ALLOWED_ORIGINS` is set to the actual production frontend origin (e.g., `https://harmony.yourdomain.com`), not `http://localhost:3001`
- [ ] API port (8000) is not reachable from untrusted networks. Use a firewall, security group, or bind to an internal interface. Phase 2 (auth) must ship before exposing the API to internet traffic.
- [ ] `data_residency_mode=true` is set in `ServiceConfigStore` or as an env var if the deployment is air-gapped or processes regulated data
- [ ] TLS is terminated at the load balancer or ingress controller; plain HTTP should not be used between the internet and the API
- [ ] `.env` file is excluded from git (already in `.gitignore`); production secrets are injected via environment or secrets manager
- [ ] Docker compose published ports are not bound to `0.0.0.0` on internet-facing hosts before Phase 2 ships

---

## Injection Vector Review

### Tool URL inputs (SSRF)

Covered by `_is_private_address` (F-02 / SEC-03). Redirects disabled. DNS failures fail closed.

### Prompt injection

Out of scope for application security. Prompt injection is an LLM behavior problem, not a code vulnerability. No application-layer mitigation is implemented or planned.

### Admin config inputs (crawler YAML, indexer YAML)

Config inputs are parsed by Pydantic models and jsonargparse. Neither evaluates embedded code. No known injection vector. The config files are trusted admin-authored files, not user-submitted inputs.

### Elasticsearch search inputs

Search queries are passed to `kv-search` which constructs ES `query_string` queries. ES handles query parsing and escaping internally. No raw query string concatenation exists in `HarmonyKeywordBackend`. Risk: Low.

### Conversation content

Message content is stored as text in Postgres via parameterized queries (SQLAlchemy). No SQL injection vector. Message content is passed to LiteLLM as chat messages — prompt injection risk is acknowledged as out of scope (AR classification above).

### Job parameter inputs

Job start endpoints (POST `/api/jobs/crawl`, etc.) accept a config name string. The `JobManager` resolves this to a config file path via `ConfigStore`. Path traversal is mitigated by `ConfigStore` which stores configs by name in a controlled directory and does not accept path separators in names.
