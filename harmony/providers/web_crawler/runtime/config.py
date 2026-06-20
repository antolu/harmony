from __future__ import annotations

import re
import typing
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from harmony.providers.web_crawler.auth.config import AuthConfig

RecrawlMode = typing.Literal["full", "age-based"]

_DOCS_DENY_DEFAULTS = [
    r"/_sources/",
    r"\.rst\.txt$",
    r"/genindex\.html$",
    r"/py-modindex\.html$",
    r"/search\.html$",
    r"/searchindex\.js$",
    r"/_modules/",
]

_DRUPAL_DENY_DEFAULTS = [r"/node/\d+"]


class AutoThrottleConfig(BaseModel):
    """AutoThrottle configuration."""

    enabled: bool = Field(
        default=True,
        description="Enable AutoThrottle for adaptive request throttling",
        title="Enabled",
    )
    start_delay: float = Field(
        default=1.0,
        description="Initial download delay for AutoThrottle (seconds)",
        title="Start delay",
    )
    max_delay: float = Field(
        default=10.0,
        description="Maximum download delay for AutoThrottle (seconds)",
        title="Max delay",
    )


class ProxyConfig(BaseModel):
    """Proxy configuration."""

    enabled: bool = Field(
        default=True, description="Enable or disable proxy", title="Enabled"
    )
    url: str = Field(
        ..., description="Proxy URL (scheme determines type)", title="Proxy URL"
    )
    username: str | None = Field(None, description="Proxy username", title="Username")
    password: str | None = Field(None, description="Proxy password", title="Password")


class DomainRoutingPattern(BaseModel):
    """Domain routing pattern configuration."""

    pattern: str = Field(
        ..., description="Regex pattern for domain matching", title="Pattern"
    )
    spider: str = Field(..., description="Spider type to use", title="Spider")


class DomainRouting(BaseModel):
    """Domain routing configuration."""

    exact: dict[str, str] = Field(
        default_factory=dict,
        description="Exact domain to spider mapping",
        title="Exact mappings",
    )
    patterns: list[DomainRoutingPattern] = Field(
        default_factory=list,
        description="Pattern-based domain routing",
        title="Pattern rules",
    )
    default: str = Field(
        "generic",
        description="Default spider for unmatched domains",
        title="Default spider",
    )


class DocsSpiderSettings(BaseModel):
    """Documentation spider settings."""

    skip_versions: bool = Field(
        default=False, description="Skip versioned paths", title="Skip versioned paths"
    )
    version_allowlist: list[str] = Field(
        default_factory=list,
        description="Allowed version paths",
        title="Version allowlist",
    )
    deny_patterns: list[str] = Field(
        default_factory=lambda: list(_DOCS_DENY_DEFAULTS),
        description="URL patterns to skip for docs sites",
        title="Deny patterns",
        json_schema_extra={"default": _DOCS_DENY_DEFAULTS},  # type: ignore
    )


class DrupalSpiderSettings(BaseModel):
    """Drupal spider settings."""

    deny_patterns: list[str] = Field(
        default_factory=lambda: list(_DRUPAL_DENY_DEFAULTS),
        description="URL patterns to skip for Drupal sites",
        title="Deny patterns",
        json_schema_extra={"default": _DRUPAL_DENY_DEFAULTS},  # type: ignore
    )


class GenericSpiderSettings(BaseModel):
    """Generic spider settings."""

    deny_patterns: list[str] = Field(
        default_factory=list,
        description="URL patterns to skip",
        title="Deny patterns",
    )


class SpiderSettings(BaseModel):
    """Spider-specific settings."""

    docs: DocsSpiderSettings = Field(
        default_factory=DocsSpiderSettings, description="Documentation spider settings"
    )
    drupal: DrupalSpiderSettings = Field(
        default_factory=DrupalSpiderSettings, description="Drupal spider settings"
    )
    generic: GenericSpiderSettings = Field(
        default_factory=GenericSpiderSettings, description="Generic spider settings"
    )


class CrawlerConfig(BaseModel):
    """Crawler configuration loaded from YAML or CLI."""

    start_urls: list[str] = Field(
        default_factory=list,
        description="URLs to start crawling from",
        title="Start URLs",
    )
    languages: list[str] = Field(
        default_factory=list,
        description="Restrict language detection to these languages",
        title="Languages",
    )
    allowed_domains: list[str] = Field(
        default_factory=list,
        description="Additional allowed domains (regex patterns)",
        title="Allowed domains",
    )
    forbidden_domains: list[str] = Field(
        default_factory=list,
        description="Domains to exclude even if they match allowed_domains (regex patterns)",
        title="Forbidden domains",
    )
    output: Path = Field(
        Path("output"), description="Output directory", title="Output directory"
    )
    max_depth: int = Field(100, description="Maximum crawl depth", title="Max depth")
    delay: float = Field(
        1.0, description="Delay between requests in seconds", title="Delay (seconds)"
    )
    concurrent: int = Field(
        5, description="Maximum concurrent requests", title="Concurrent requests"
    )
    verbose: int = Field(
        0, description="Verbosity level (0=INFO, 1+=DEBUG)", title="Verbosity"
    )
    proxy: ProxyConfig | None = Field(
        None, description="Proxy configuration", title="Proxy"
    )
    domain_routing: DomainRouting = Field(
        default_factory=DomainRouting,  # type: ignore
        description="Domain to spider routing",
        title="Domain routing",
    )
    spider_settings: SpiderSettings = Field(
        default_factory=SpiderSettings,
        description="Spider-specific settings",
        title="Spider settings",
    )

    recrawl_mode: RecrawlMode = Field(
        "full", description="Re-crawl mode (full or age-based)", title="Recrawl mode"
    )
    max_age_days: int = Field(
        30,
        description="Max age in days for age-based re-crawling",
        title="Max age (days)",
    )
    delete_missing: bool = Field(
        default=False,
        description="Automatically delete URLs missing for threshold crawls",
        title="Delete missing URLs",
    )
    missing_threshold: int = Field(
        3,
        description="Number of crawls before marking URL for deletion",
        title="Missing threshold",
    )
    safe_mode: bool = Field(
        default=False,
        description="Enable extra strict safety checks",
        title="Safe mode",
    )
    dry_run: bool = Field(
        default=False,
        description="Dry run mode (log URLs but don't request)",
        title="Dry run",
    )
    allow_mutations: bool = Field(
        default=False,
        description="Allow mutation endpoints (edit, update, delete) - USE WITH CAUTION",
        title="Allow mutations",
    )
    ignore_robots: bool = Field(
        default=False,
        description="Ignore robots.txt (not recommended)",
        title="Ignore robots.txt",
    )
    safety_allow_list: list[str] = Field(
        default_factory=list,
        description="Regex patterns for URLs to allow (bypasses safety checks)",
        title="Safety allow list",
    )
    safety_deny_list: list[str] = Field(
        default_factory=list,
        description="Additional regex patterns for URLs to block",
        title="Safety deny list",
    )
    link_extractor_deny: list[str] = Field(
        default_factory=list,
        description="Regex patterns for URLs to skip (scope filtering, not safety)",
        title="Link extractor deny",
    )
    interactive_safety: bool = Field(
        default=False,
        description="Prompt user to approve/deny blocked URLs interactively",
        title="Interactive safety",
    )
    autothrottle: AutoThrottleConfig = Field(
        default_factory=AutoThrottleConfig,
        description="AutoThrottle configuration",
        title="AutoThrottle",
    )
    download_timeout: float = Field(
        default=180.0,
        description="Request timeout in seconds",
        title="Download timeout (seconds)",
    )
    auth: AuthConfig | None = Field(
        None,
        description="Authentication configuration for protected sites",
        title="Authentication",
    )

    @model_validator(mode="before")
    @classmethod
    def migrate_autothrottle(cls, data: dict[str, typing.Any]) -> dict[str, typing.Any]:
        """Migrate flat autothrottle settings to nested structure."""
        if not isinstance(data, dict):
            return data

        # Collect flat keys
        enabled = data.pop("autothrottle_enabled", None)
        start_delay = data.pop("autothrottle_start_delay", None)
        max_delay = data.pop("autothrottle_max_delay", None)

        # If any flat keys exist, move them to nested 'autothrottle' object
        if enabled is not None or start_delay is not None or max_delay is not None:
            autothrottle = data.get("autothrottle", {})
            if isinstance(autothrottle, dict):
                if enabled is not None:
                    autothrottle["enabled"] = enabled
                if start_delay is not None:
                    autothrottle["start_delay"] = start_delay
                if max_delay is not None:
                    autothrottle["max_delay"] = max_delay
                data["autothrottle"] = autothrottle

        return data

    @property
    def default_spider(self) -> str:
        """Get default spider name."""
        return self.domain_routing.default

    def get_spider_for_domain(self, domain: str) -> str:
        """Determine which spider to use for a given domain.

        Priority:
        1. Exact match
        2. Pattern match (in order)
        3. Default spider
        """
        if domain in self.domain_routing.exact:
            return self.domain_routing.exact[domain]

        for pattern_config in self.domain_routing.patterns:
            if re.search(pattern_config.pattern, domain):
                return pattern_config.spider

        return self.default_spider

    def get_spider_settings_for(
        self, spider_name: str
    ) -> (
        DocsSpiderSettings
        | DrupalSpiderSettings
        | GenericSpiderSettings
        | dict[str, typing.Any]
        | None
    ):
        """Get settings for a specific spider."""
        if spider_name == "docs":
            return self.spider_settings.docs
        if spider_name == "drupal":
            return self.spider_settings.drupal
        if spider_name == "generic":
            return self.spider_settings.generic
        return None
