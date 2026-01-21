# Creating Custom Authentication Providers

Harmony's authentication system is fully extensible. Companies can add custom auth providers **without modifying Harmony's source code**.

## How It Works

Harmony uses Python entry points for plugin discovery. When Harmony starts:
1. It scans installed packages for the `harmony.auth_providers` entry point group
2. Automatically loads and registers any custom providers found
3. Makes them available for use in `harmony_config.yaml`

## Quick Start (3 Steps)

### Step 1: Create Provider Class

Create a new Python package with your provider:

```python
# my_company_auth/provider.py
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from harmony.crawler.auth.providers.base import AuthProvider
from harmony.crawler.auth.session import AuthSession

if TYPE_CHECKING:
    from scrapy import Request
    from scrapy.http import Response


class MyCompanySSO(AuthProvider):
    """Custom SSO authentication provider."""

    def __init__(self, config) -> None:
        # Extract domains for base class
        # Config uses 'domains' field
        super().__init__(config.domains)
        self.config = config
        
        # Access your custom config fields
        self.sso_endpoint = getattr(config, 'sso_endpoint', None)
        self.client_id = getattr(config, 'client_id', None)

    @property
    def provider_type(self) -> str:
        """Must match your entry point name."""
        return "my_company_sso"

    async def authenticate(
        self, subdomain: str, trigger_url: str | None = None
    ) -> AuthSession:
        """Perform authentication and return session."""
        # Your authentication logic here
        # Example: OAuth2 flow, SAML, API token exchange, etc.
        
        return AuthSession(
            provider_type=self.provider_type,
            subdomain=subdomain,
            domain_pattern=self.get_matching_pattern(subdomain) or "",
            created_at=datetime.now(),
            headers={"Authorization": f"Bearer {access_token}"},
        )

    def apply_to_request(self, request: Request, session: AuthSession) -> Request:
        """Apply credentials from session to request."""
        for header, value in session.headers.items():
            request.headers[header.encode()] = value.encode()
        return request
```

### Step 2: Register Entry Point

In your package's `pyproject.toml`:

```toml
[project]
name = "my-company-auth"
version = "1.0.0"
dependencies = ["harmony"]

[project.entry-points."harmony.auth_providers"]
my_company_sso = "my_company_auth.provider:MyCompanySSO"
```

> [!IMPORTANT]
> The entry point name (`my_company_sso`) **must match** the `provider_type` property.

### Step 3: Install and Use

```bash
pip install my-company-auth
```

Configure in `harmony_config.yaml`:

```yaml
auth:
  providers:
    - type: my_company_sso  # Matches entry point name
      domains: [".*\\.mycompany\\.com"]
      # Custom fields for your provider:
      sso_endpoint: "https://sso.mycompany.com/oauth"
      client_id: "harmony_crawler"
```

**That's it!** Harmony automatically discovers and uses your provider.

---

## Provider Interface

### Required Methods

| Method | Description |
|--------|-------------|
| `provider_type` | Property returning unique identifier (must match entry point name) |
| `authenticate()` | Perform auth, return `AuthSession` with credentials |
| `apply_to_request()` | Apply session credentials to outgoing Scrapy request |

### Optional Overrides

| Method | Default | Override When |
|--------|---------|---------------|
| `is_interactive()` | `False` | Provider requires user interaction (browser login, 2FA) |
| `is_auth_required()` | Checks 401/403 | Detect provider-specific auth failures (redirects, custom headers) |
| `matches_domain()` | Regex match | Custom domain matching logic |

---

## Configuration Schema

Your provider receives a config object with:
- `type` (str) - Provider type identifier
- `domains` (list[str]) - Regex patterns for domains
- **Any additional fields** you define in YAML

The `CustomAuthConfig` class accepts arbitrary fields via `extra="allow"`, so you can define any config structure your provider needs.

---

## Best Practices

### Error Handling
```python
async def authenticate(self, subdomain, trigger_url=None):
    try:
        tokens = await self._fetch_tokens()
    except AuthError as e:
        logger.error(f"Auth failed for {subdomain}: {e}")
        raise
```

### Token Refresh
```python
from datetime import timedelta

async def authenticate(self, subdomain, trigger_url=None):
    return AuthSession(
        # ...
        expires_at=datetime.now() + timedelta(seconds=3600),
    )
```

Harmony's middleware automatically triggers re-auth when sessions expire.

### Logging
```python
from harmony.crawler.logger import logger

logger.info(f"Starting {self.provider_type} auth for {subdomain}")
```

---

## Testing Your Provider

```python
# tests/test_my_provider.py
import pytest
from my_company_auth.provider import MyCompanySSO

class MockConfig:
    type = "my_company_sso"
    domains = [".*\\.mycompany\\.com"]
    sso_endpoint = "https://sso.test.com"

def test_provider_type():
    provider = MyCompanySSO(MockConfig())
    assert provider.provider_type == "my_company_sso"

def test_domain_matching():
    provider = MyCompanySSO(MockConfig())
    assert provider.matches_domain("app.mycompany.com")
    assert not provider.matches_domain("example.com")

@pytest.mark.asyncio
async def test_authentication():
    provider = MyCompanySSO(MockConfig())
    session = await provider.authenticate("app.mycompany.com")
    assert session.provider_type == "my_company_sso"
```

---

## Package Structure

```
my-company-auth/
├── pyproject.toml
├── README.md
├── src/
│   └── my_company_auth/
│       ├── __init__.py
│       └── provider.py
└── tests/
    └── test_provider.py
```

---

## Example Implementations

### OAuth2 Client Credentials

```python
class OAuth2Provider(AuthProvider):
    async def authenticate(self, subdomain, trigger_url=None):
        async with httpx.AsyncClient() as client:
            response = await client.post(self.config.token_url, data={
                "grant_type": "client_credentials",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
            })
            data = response.json()
            
            return AuthSession(
                provider_type=self.provider_type,
                subdomain=subdomain,
                domain_pattern=self.get_matching_pattern(subdomain) or "",
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(seconds=data["expires_in"]),
                headers={"Authorization": f"Bearer {data['access_token']}"},
            )
```

### Simple API Key

```python
class APIKeyProvider(AuthProvider):
    async def authenticate(self, subdomain, trigger_url=None):
        return AuthSession(
            provider_type=self.provider_type,
            subdomain=subdomain,
            domain_pattern=self.get_matching_pattern(subdomain) or "",
            created_at=datetime.now(),
            headers={"X-API-Key": self.config.api_key},
        )
```
