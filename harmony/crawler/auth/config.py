from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class StaticCookieAuthConfig(BaseModel):
    """Static cookie authentication configuration."""

    type: Literal["static_cookie"] = "static_cookie"
    domains: list[str] = Field(
        description="Regex patterns for domains this provider handles"
    )
    cookies: dict[str, str] | None = Field(
        default=None, description="Cookie name-value pairs"
    )
    cookie_file: Path | None = Field(
        default=None, description="Path to file containing cookies"
    )


class BasicAuthConfig(BaseModel):
    """HTTP Basic authentication configuration."""

    type: Literal["basic"] = "basic"
    domains: list[str] = Field(
        description="Regex patterns for domains this provider handles"
    )
    username: str
    password: str


class BearerTokenAuthConfig(BaseModel):
    """Bearer token authentication configuration."""

    type: Literal["bearer"] = "bearer"
    domains: list[str] = Field(
        description="Regex patterns for domains this provider handles"
    )
    token: str
    header_name: str = Field(default="Authorization")
    header_prefix: str = Field(default="Bearer")


class ServiceAccountAuthConfig(BaseModel):
    """OAuth2 client credentials (service account) configuration."""

    type: Literal["service_account"] = "service_account"
    domains: list[str] = Field(
        description="Regex patterns for domains this provider handles"
    )
    client_id: str
    client_secret: str
    token_url: str
    scope: str | None = None
    token_expiry_buffer_seconds: int = Field(
        default=60, description="Refresh token this many seconds before expiry"
    )


class PlaywrightSSOAuthConfig(BaseModel):
    """Interactive SSO authentication via Playwright."""

    type: Literal["playwright_sso"] = "playwright_sso"
    name: str = Field(
        description="Human-readable name for this SSO provider (e.g., 'cern-sso')"
    )
    domains: list[str] = Field(
        description="Regex patterns for domains this provider handles"
    )
    login_url: str | None = Field(
        default=None, description="URL to start the SSO login flow"
    )
    storage_state_file: Path | None = Field(
        default=None, description="Path to save/load Playwright storage state"
    )
    success_url_pattern: str | None = Field(
        default=None,
        description="Regex pattern to detect successful login (URL after auth completes)",
    )
    login_complete_marker: str | None = Field(
        default=None, description="Text or element to wait for on successful login page"
    )
    user_agent: str = Field(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        description="User-Agent string to use in Playwright browser",
    )
    headless: bool = Field(
        default=False,
        description="Run browser in headless mode (set False for interactive 2FA)",
    )
    browser_type: Literal["chromium", "firefox", "webkit"] = Field(default="chromium")
    timeout_seconds: int = Field(
        default=300, description="Timeout for interactive login (seconds)"
    )
    proxy: dict[str, str] | None = Field(
        default=None, description="Proxy settings (injected from global config)"
    )


class CustomAuthConfig(BaseModel):
    """Configuration for custom authentication providers.

    This allows third-party packages to define custom authentication providers
    without modifying Harmony's core code.

    Example usage in config:
        providers:
          - type: my_custom_auth
            domains: ["api\\.example\\.com"]
            custom_param_1: "value1"
            custom_param_2: 123

    The custom provider is loaded via entry point:
        [project.entry-points."harmony.auth_providers"]
        my_custom_auth = "my_package.auth:MyCustomAuth"
    """

    model_config = {"extra": "allow"}

    type: str = Field(description="Custom provider type name")
    domains: list[str] = Field(
        description="Regex patterns for domains this provider handles"
    )


# Note: We can't use Pydantic discriminator with CustomAuthConfig since it has
# a dynamic type field. The registry will handle provider instantiation.
AuthProviderConfig = (
    StaticCookieAuthConfig
    | BasicAuthConfig
    | BearerTokenAuthConfig
    | ServiceAccountAuthConfig
    | PlaywrightSSOAuthConfig
    | CustomAuthConfig
)


class AuthConfig(BaseModel):
    """Root authentication configuration."""

    enabled: bool = Field(default=True, description="Enable authentication middleware")
    session_storage_path: Path = Field(
        default=Path(".harmony-auth-sessions"),
        description="Directory to store session data",
    )
    retry_on_auth_failure: bool = Field(
        default=True, description="Automatically retry requests after re-authentication"
    )
    max_auth_retries: int = Field(
        default=2, description="Maximum authentication retry attempts per request"
    )
    auto_authenticate_on_403: bool = Field(
        default=True,
        description="Automatically trigger authentication when 403 is encountered",
    )
    providers: list[AuthProviderConfig] = Field(
        default_factory=list,
        description="List of authentication provider configurations",
    )
