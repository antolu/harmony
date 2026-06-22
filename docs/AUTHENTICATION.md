# Authentication Guide

Harmony's crawler supports multiple authentication methods for crawling protected sites. This guide covers all authentication providers, configuration, and usage.

## Table of Contents

- [Overview](#overview)
- [Authentication Providers](#authentication-providers)
  - [Static Cookie Authentication](#static-cookie-authentication)
  - [HTTP Basic Authentication](#http-basic-authentication)
  - [Bearer Token Authentication](#bearer-token-authentication)
  - [OAuth2 Service Account](#oauth2-service-account)
  - [OIDC (Client Credentials / Authorization Code)](#oidc-client-credentials--authorization-code)
  - [Interactive SSO with Playwright](#interactive-sso-with-playwright)
- [Configuration](#configuration)
- [CLI Usage](#cli-usage)
- [Architecture](#architecture)
- [Examples](#examples)

## Overview

Harmony's authentication system is designed to be:

- **Pluggable** - Multiple authentication methods supported
- **Per-subdomain** - Different credentials for different parts of a site
- **Persistent** - Sessions saved to disk and reused across crawls
- **Automatic** - Auto-retry on authentication failures
- **Interactive** - Support for complex SSO flows with 2FA

### Key Features

- 6 authentication provider types
- Domain pattern matching with regex
- Per-subdomain session tracking
- Automatic session persistence (Postgres + Redis)
- Auto-refresh for OAuth2 tokens
- Browser automation for interactive SSO
- Automatic retry on 401/403 responses
- CLI for session management

## Authentication Providers

### Static Cookie Authentication

Simplest method for sites where you've already obtained cookies (e.g., from browser dev tools).

**Use cases:**
- Sites with complex login flows
- When you have valid cookies from a browser session
- Quick testing with known-good credentials

**Configuration:**
```yaml
crawler:
  auth:
    providers:
      - type: static_cookie
        domains:
          - "protected\\.example\\.com"
          - "secure\\.site\\.com"
        cookies:
          session_id: "abc123xyz"
          auth_token: "secret_token"
          # Add any cookies the site requires
```

**Pros:**
- Very simple setup
- No additional dependencies
- Works with any authentication scheme

**Cons:**
- Manual cookie extraction required
- Cookies may expire
- No automatic refresh

### HTTP Basic Authentication

Standard HTTP Basic Auth (username/password in Authorization header).

**Use cases:**
- APIs with Basic Auth
- Simple authenticated endpoints
- Development/staging servers

**Configuration:**
```yaml
crawler:
  auth:
    providers:
      - type: basic
        domains:
          - "api\\.example\\.com"
        username: "myuser"
        password: "mypassword"
```

**Pros:**
- Simple and standardized
- Widely supported
- No external dependencies

**Cons:**
- Not suitable for complex auth flows
- Credentials sent with every request

### Bearer Token Authentication

OAuth2 access tokens or API tokens in Authorization header.

**Use cases:**
- APIs requiring bearer tokens
- Pre-obtained OAuth2 access tokens
- API key authentication

**Configuration:**
```yaml
crawler:
  auth:
    providers:
      - type: bearer
        domains:
          - "api\\.example\\.com"
        token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Pros:**
- Simple for token-based APIs
- Stateless
- No password transmission

**Cons:**
- Manual token management
- No automatic refresh
- Tokens expire

### OAuth2 Service Account

OAuth2 Client Credentials flow with automatic token refresh.

**Use cases:**
- Service-to-service authentication
- APIs with OAuth2 client credentials
- Automated crawling with service accounts

**Configuration:**
```yaml
crawler:
  auth:
    providers:
      - type: service_account
        domains:
          - "api\\.example\\.com"
        token_url: "https://auth.example.com/oauth/token"
        client_id: "service_account_id"
        client_secret: "service_account_secret"
        scopes:
          - "read:data"
          - "write:data"
```

**How it works:**
1. Provider exchanges client credentials for access token
2. Token cached and reused until expiration
3. Automatic refresh when token expires
4. New token obtained transparently

**Pros:**
- Fully automatic token management
- Secure (no user passwords)
- Scalable for automation

**Cons:**
- Requires OAuth2 server support
- More complex setup

### OIDC (Client Credentials / Authorization Code)

OIDC provider with discovery (`{issuer_url}/.well-known/openid-configuration`), supporting both `client_credentials` (service-to-service) and `authorization_code` with PKCE (interactive login) flows.

**Use cases:**
- Crawling sites protected by an OIDC-compliant IdP (Keycloak, Okta, Azure AD)
- Service-to-service crawling without storing static secrets
- Interactive login flows that still benefit from automatic token refresh

**Configuration:**
```yaml
crawler:
  auth:
    providers:
      - type: oidc
        name: "internal-oidc"
        domains:
          - "internal\\.example\\.com"
        issuer_url: "https://idp.example.com/realms/example"
        client_id: "crawler-client"
        client_secret: "${OIDC_CLIENT_SECRET}"
        flow: client_credentials  # or "authorization_code"
        scopes: ["openid", "offline_access"]
```

**Pros:**
- Standards-based discovery, no manual token-endpoint configuration
- Automatic refresh for both flows
- Works with any OIDC-compliant IdP

**Cons:**
- `authorization_code` flow is interactive (requires a one-time browser login, see Playwright SSO below for the headless flow)

### Interactive SSO with Playwright

Browser automation for complex authentication flows (SSO, SAML, 2FA, etc.).

**Use cases:**
- Corporate SSO (Okta, Azure AD, Google Workspace, etc.)
- Sites with 2FA/MFA requirements
- Complex login flows (SAML, OAuth2 authorization code)
- Sites that block non-browser user agents

**Requirements:**
```bash
# Install browser dependencies
pip install harmony[browser]

# Install Chromium (only needed once)
playwright install chromium
```

**Configuration:**
```yaml
crawler:
  auth:
    providers:
      - type: playwright_sso
        name: "corporate-sso"
        domains:
          - "sso\\.company\\.com"
          - ".*\\.internal\\.company\\.com"
        login_url: "https://sso.company.com/login"
        storage_state_file: ".sso-state.json"
        # Optional: success URL pattern to detect login completion
        success_url_pattern: ".*/dashboard.*"
```

**How it works:**
1. On first auth attempt, Playwright opens a browser window
2. User logs in manually (can handle 2FA, CAPTCHA, etc.)
3. Browser state (cookies, localStorage) saved to disk
4. Subsequent requests reuse saved state
5. On session expiry, browser opens again for re-auth

**Browser state storage:**
- Persisted to Postgres, cached in Redis
- Includes cookies, localStorage, sessionStorage
- Reused across crawls
- Per-subdomain tracking

**Pros:**
- Handles any authentication flow
- Supports 2FA/MFA
- Works with SSO providers
- User-driven (no reverse engineering needed)

**Cons:**
- Requires browser installation
- Interactive (not fully automated)
- Slower than API-based auth
- Browser state can expire

**Best practices:**
- Use for initial login only
- Let crawler reuse saved state
- Use `harmony-auth login` to pre-authenticate before crawls
- Store state files securely

## Configuration

### Full Configuration Example

```yaml
crawler:
  auth:
    # Retry settings for failed authentication
    max_auth_retries: 3
    auth_retry_delay: 5.0

    # Multiple providers supported
    providers:
      # Static cookies for main site
      - type: static_cookie
        domains:
          - "www\\.example\\.com"
        cookies:
          session: "abc123"

      # Basic auth for API
      - type: basic
        domains:
          - "api\\.example\\.com"
        username: "api_user"
        password: "api_pass"

      # Service account for internal API
      - type: service_account
        domains:
          - "internal-api\\.example\\.com"
        token_url: "https://auth.example.com/token"
        client_id: "service_id"
        client_secret: "service_secret"
        scopes: ["read:all"]

      # Interactive SSO for intranet
      - type: playwright_sso
        name: "intranet-sso"
        domains:
          - "intranet\\.company\\.com"
          - ".*\\.internal\\.company\\.com"
        login_url: "https://sso.company.com/login"
```

### Domain Pattern Matching

Domain patterns use Python regex to match subdomains:

```yaml
domains:
  - "docs\\.example\\.com"              # Exact: docs.example.com
  - ".*\\.example\\.com"                # Any subdomain of example.com
  - "(api|www)\\.example\\.com"         # api or www subdomains
  - "secure-.*\\.example\\.com"         # Subdomains starting with "secure-"
```

**Important:** Remember to escape dots (`\.`) in domain names.

### Environment Variables

Sensitive credentials can use environment variables:

```yaml
crawler:
  auth:
    providers:
      - type: basic
        domains: ["api\\.example\\.com"]
        username: "${API_USERNAME}"
        password: "${API_PASSWORD}"
```

Set in `.env` file:
```bash
API_USERNAME=myuser
API_PASSWORD=mypass
```

## CLI Usage

The `harmony-auth` CLI helps manage authentication sessions.

### Interactive Login

Pre-authenticate before crawling:

```bash
harmony-auth login
```

This will:
1. Load auth config from `harmony_config.yaml`
2. Show all configured providers
3. Prompt to select a provider
4. For interactive SSO, open browser for login
5. Save session for reuse

### View Status

Check provider configuration and active sessions:

```bash
harmony-auth status
```

Output shows:
- Configured providers with domain patterns
- Active sessions per subdomain
- Session validity (for OAuth2 tokens)
- Storage state status (for Playwright)

Example output:
```
Authentication Providers
┌──────────────────────┬────────────────┬──────────────────────────────┐
│ Provider ID          │ Type           │ Domains                      │
├──────────────────────┼────────────────┼──────────────────────────────┤
│ basic-api            │ basic          │ api\.example\.com            │
│ sso-intranet         │ playwright_sso │ intranet\.company\.com       │
└──────────────────────┴────────────────┴──────────────────────────────┘

Active Sessions
┌─────────────────────────────┬──────────────────────┬─────────────────────┐
│ Subdomain                   │ Provider             │ Expires             │
├─────────────────────────────┼──────────────────────┼─────────────────────┤
│ api.example.com             │ basic-api            │ Never               │
│ intranet.company.com        │ sso-intranet         │ 2026-01-11 12:34:56 │
└─────────────────────────────┴──────────────────────┴─────────────────────┘
```

### Clear Sessions

Remove all saved sessions:

```bash
harmony-auth clear
```

This will:
- Delete all session files
- Remove Playwright storage states
- Prompt for confirmation

Use cases:
- Sessions expired or invalid
- Switch authentication credentials
- Testing with fresh state

### Config File Path

By default, CLI uses `harmony_config.yaml` in current directory. Specify a different file:

```bash
harmony-auth status --config /path/to/config.yaml
harmony-auth login --config /path/to/config.yaml
```

## Architecture

### Components

```
AuthProviderRegistry
  ├─ Loads providers from config
  ├─ Manages sessions per subdomain
  ├─ Persists to Postgres + Redis
  └─ Thread-safe access
         ↓
AuthMiddleware (Scrapy, priority 50)
  ├─ Checks if domain requires auth
  ├─ Applies credentials to requests
  ├─ Detects auth failures (401/403)
  ├─ Triggers re-authentication
  └─ Retries requests with new credentials
         ↓
AuthProvider (base class)
  ├─ StaticCookieAuthProvider
  ├─ BasicAuthProvider
  ├─ BearerTokenAuthProvider
  ├─ ServiceAccountAuthProvider
  └─ PlaywrightSSOAuthProvider
```

### Middleware Priority

Middlewares execute in priority order (lower = earlier):

- **50** - AuthMiddleware (apply credentials)
- **100** - SafetyMiddleware (safety checks)
- **500** - AllowedDomainsMiddleware (domain filtering)
- **543** - DomainRouterMiddleware (spider routing)
- **544** - DeltaFetchMiddleware (change detection)

Auth runs first to ensure all subsequent middlewares have authenticated requests.

### Session Storage

Sessions are persisted to Postgres and cached in Redis. Each session
is keyed by subdomain and stores provider credentials (cookies,
headers), expiry, and creation time. Playwright browser state for SSO
providers is stored alongside the session record.

### Authentication Flow

1. **Request Creation**
   - Spider generates request
   - Request enters middleware pipeline

2. **Auth Check** (AuthMiddleware)
   - Extract subdomain from URL
   - Check if provider matches domain
   - If session exists, apply credentials

3. **Request Execution**
   - Request sent to server
   - Response received

4. **Response Handling** (AuthMiddleware)
   - Check response status
   - If 401/403 (auth required):
     - Trigger provider.authenticate()
     - Save new session
     - Retry request with new credentials
   - If 200-399: pass response through

5. **Session Persistence**
   - On spider close, save sessions to disk
   - On spider open, load sessions from disk

### Provider Selection

Multiple providers can be configured. The registry selects the provider whose domain pattern matches the request:

```python
# Request: https://api.example.com/users
# Matches: provider with pattern "api\.example\.com"

# Request: https://docs.example.com/guide
# Matches: provider with pattern ".*\.example\.com"
```

First matching provider is used. Order matters in config.

## Examples

### Example 1: Simple API with Basic Auth

```yaml
crawler:
  start_urls:
    - "https://api.example.com/docs"

  auth:
    providers:
      - type: basic
        domains: ["api\\.example\\.com"]
        username: "api_user"
        password: "secret123"
```

```bash
harmony-crawl --config config.yaml
```

### Example 2: Corporate Intranet with SSO

```yaml
crawler:
  start_urls:
    - "https://wiki.company.com"
    - "https://docs.company.com"

  auth:
    providers:
      - type: playwright_sso
        domains:
          - ".*\\.company\\.com"
        login_url: "https://sso.company.com/login"
        storage_state_file: ".company-sso.json"
```

```bash
# Pre-authenticate (opens browser for login)
harmony-auth login

# Crawl (reuses saved session)
harmony-crawl --config config.yaml
```

### Example 3: Multi-Provider Setup

```yaml
crawler:
  start_urls:
    - "https://public.example.com"    # No auth needed
    - "https://api.example.com"       # Basic auth
    - "https://portal.example.com"    # SSO

  auth:
    providers:
      # API endpoints
      - type: basic
        domains: ["api\\.example\\.com"]
        username: "api_user"
        password: "api_pass"

      # Portal with SSO
      - type: playwright_sso
        domains: ["portal\\.example\\.com"]
        login_url: "https://portal.example.com/login"
        storage_state_file: ".portal-sso.json"

      # Internal services with OAuth2
      - type: service_account
        domains: ["internal\\.example\\.com"]
        token_url: "https://auth.example.com/token"
        client_id: "crawler_service"
        client_secret: "${SERVICE_SECRET}"
        scopes: ["read:all"]
```

### Example 4: Pre-obtained Cookies

```bash
# Get cookies from browser (Chrome DevTools → Application → Cookies)
# Copy cookie values
```

```yaml
crawler:
  auth:
    providers:
      - type: static_cookie
        domains: ["secure\\.site\\.com"]
        cookies:
          sessionid: "abc123def456"
          csrftoken: "xyz789uvw012"
          auth_token: "bearer_token_here"
```

### Example 5: OAuth2 Service Account with Scopes

```yaml
crawler:
  auth:
    providers:
      - type: service_account
        domains:
          - "api\\.example\\.com"
          - "data\\.example\\.com"
        token_url: "https://oauth.example.com/v2/token"
        client_id: "crawler_client_id"
        client_secret: "${OAUTH_SECRET}"
        scopes:
          - "https://example.com/auth/readonly"
          - "https://example.com/auth/metadata.read"
```

**Token refresh:**
- Automatic when token expires
- No manual intervention needed
- Transparent to crawler

### Example 6: Interactive SSO with Custom Auth Detection

```yaml
crawler:
  auth:
    providers:
      - type: playwright_sso
        name: "company-sso"
        domains: ["sso\\.company\\.com"]
        login_url: "https://sso.company.com/login"
        storage_state_file: ".sso-state.json"
        # Override retry settings for this provider
        max_retries: 2
        retry_delay: 10.0
```

## Troubleshooting

### Sessions Not Persisting

**Problem:** Sessions don't persist between crawls.

**Solution:**
- Verify Postgres and Redis are running and reachable
- Check crawler logs for session save/load errors

### Authentication Keeps Failing

**Problem:** 401/403 errors despite configuration.

**Solution:**
1. Check domain patterns match exactly:
   ```bash
   harmony-auth status  # Shows patterns
   ```
2. Test provider independently:
   ```bash
   harmony-auth login   # Manual auth test
   ```
3. Check provider credentials are correct
4. For SSO, try clearing and re-authenticating:
   ```bash
   harmony-auth clear
   harmony-auth login
   ```

### Playwright Browser Not Opening

**Problem:** Interactive SSO doesn't open browser.

**Solution:**
```bash
# Install browser if missing
playwright install chromium

# Check installation
playwright --version

# Reinstall if needed
pip uninstall playwright
pip install harmony[browser]
playwright install chromium
```

### OAuth2 Token Not Refreshing

**Problem:** Service account auth fails after token expires.

**Solution:**
- Verify `token_url` is correct
- Check `client_id` and `client_secret`
- Ensure scopes are valid
- Check server supports token refresh
- Look for `expires_in` in token response

### Multiple Subdomains, One Provider

**Problem:** Need same auth for many subdomains.

**Solution:** Use broad pattern:
```yaml
domains:
  - ".*\\.example\\.com"  # Matches all subdomains
```

Sessions are still tracked per subdomain internally.

### Cookies Not Being Sent

**Problem:** Static cookies configured but not appearing in requests.

**Solution:**
- Check cookie names match server expectations
- Verify domain pattern matches request domain
- Check for cookie domain/path restrictions
- Look for `Secure` or `HttpOnly` flags in browser cookies

### Session Expires During Long Crawl

**Problem:** Authentication fails mid-crawl.

**Solution:**
- For static cookies: Not much you can do, use other methods
- For OAuth2: Should auto-refresh (check configuration)
- For SSO: May need manual re-auth if session TTL is short
- Consider using service accounts for long-running crawls

## Best Practices

1. **Use service accounts for automation**
   - More reliable than user accounts
   - No MFA interruptions
   - Better for CI/CD

2. **Pre-authenticate before large crawls**
   ```bash
   harmony-auth login
   harmony-crawl --config config.yaml
   ```

3. **Store secrets in environment variables**
   ```yaml
   username: "${API_USER}"
   password: "${API_PASS}"
   ```

4. **Use specific domain patterns**
   ```yaml
   # Good: specific
   domains: ["api\\.example\\.com"]

   # Bad: too broad
   domains: [".*"]
   ```

5. **Test authentication separately**
   ```bash
   # Test with dry run
   harmony-crawl --config config.yaml --crawler.dry_run

   # Check auth status
   harmony-auth status
   ```

6. **Monitor session expiry**
   - Check `harmony-auth status` regularly
   - Set up alerts for long-running crawls
   - Use OAuth2 with refresh for long sessions

7. **Keep session storage secure**
   - Sessions in Postgres contain credentials
   - Restrict database access in production
   - Use TLS for Postgres and Redis connections

8. **Use appropriate auth method**
   - Static cookies: Testing, temporary
   - Basic Auth: Simple APIs
   - Bearer tokens: Modern APIs (short-lived)
   - Service accounts: Automation (best for production)
   - Interactive SSO: Human-driven, initial setup

## Security Considerations

1. **Credential Storage**
   - Sessions stored in Postgres, cached in Redis
   - Restrict database access and use TLS in production

2. **Environment Variables**
   - Preferred for sensitive values
   - Don't commit `.env` files
   - Use secret management in production

3. **Browser State**
   - Playwright stores full browser state
   - Includes all cookies and storage
   - Treat as sensitive credentials

4. **Token Expiry**
   - OAuth2 tokens expire and refresh automatically
   - Static tokens/cookies don't refresh
   - Monitor and rotate credentials regularly

5. **Logging**
   - Auth credentials not logged
   - Session IDs may appear in debug logs
   - Use appropriate log levels in production

## Advanced Topics

### Custom Authentication Providers (Extensibility)

Harmony supports custom auth providers via Python entry points. **No Harmony code changes required.**

Third-party packages can provide custom auth providers that are automatically discovered:

1. **Create provider class** (in your package):
```python
from harmony.providers.web_crawler.auth.providers.base import AuthProvider
from harmony.providers.web_crawler.auth.session import AuthSession

class MyCustomAuth(AuthProvider):
    @property
    def provider_type(self) -> str:
        return "my_custom_auth"  # Must match entry point name

    async def authenticate(self, subdomain, trigger_url=None) -> AuthSession:
        # Your auth logic here
        ...

    def apply_to_request(self, request, session):
        # Apply credentials to request
        ...
```

2. **Register via entry point** (in your `pyproject.toml`):
```toml
[project.entry-points."harmony.auth_providers"]
my_custom_auth = "my_package.auth:MyCustomAuth"
```

3. **Use in config** (no Harmony changes needed):
```yaml
auth:
  providers:
    - type: my_custom_auth  # Automatically discovered!
      domains: [".*\\.example\\.com"]
      custom_option: "value"  # Any fields accepted
```

For detailed implementation guide, see [CUSTOM_AUTH_PROVIDER.md](CUSTOM_AUTH_PROVIDER.md).

### Session Lifecycle Hooks

Override provider methods for custom behavior:

```python
class CustomProvider(AuthProvider):
    async def on_session_created(self, session: AuthSession) -> None:
        # Called after successful authentication
        pass

    async def on_session_expired(self, session: AuthSession) -> None:
        # Called when session expires
        pass

    async def on_auth_failed(self, error: Exception) -> None:
        # Called when authentication fails
        pass
```

### Programmatic Usage

Use authentication system in custom scripts:

```python
from harmony.providers.web_crawler.auth.config import AuthConfig
from harmony.providers.web_crawler.auth.registry import AuthProviderRegistry

# Load config
auth_config = AuthConfig.from_yaml("harmony_config.yaml")

# Create registry
registry = AuthProviderRegistry(auth_config)

# Get provider for domain
provider = registry.get_provider_for_domain("api.example.com")

# Authenticate
session = await provider.authenticate("api.example.com")

# Use session
print(f"Session: {session.credentials}")
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/antolu/harmony/issues
- Documentation: https://github.com/antolu/harmony
- Examples: `harmony_config.example.yaml`

## Changelog

- **v1.0.0** (2026-01-10)
  - Initial authentication system
  - 5 provider types
  - CLI for session management
  - Per-subdomain tracking
  - Automatic retry on auth failure
