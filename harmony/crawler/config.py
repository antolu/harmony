from __future__ import annotations

import re
import typing
from pathlib import Path

from pydantic import BaseModel, Field

from harmony.crawler.auth.config import AuthConfig

RecrawlMode = typing.Literal["full", "age-based"]


class ProxyConfig(BaseModel):
    """Proxy configuration."""

    url: str = Field(..., description="Proxy URL (scheme determines type)")
    username: str | None = Field(None, description="Proxy username")
    password: str | None = Field(None, description="Proxy password")


class DomainRoutingPattern(BaseModel):
    """Domain routing pattern configuration."""

    pattern: str = Field(..., description="Regex pattern for domain matching")
    spider: str = Field(..., description="Spider type to use")


class DomainRouting(BaseModel):
    """Domain routing configuration."""

    exact: dict[str, str] = Field(
        default_factory=dict, description="Exact domain to spider mapping"
    )
    patterns: list[DomainRoutingPattern] = Field(
        default_factory=list, description="Pattern-based domain routing"
    )
    default: str = Field("generic", description="Default spider for unmatched domains")


class DocsSpiderSettings(BaseModel):
    """Documentation spider settings."""

    skip_versions: bool = Field(default=False, description="Skip versioned paths")
    version_allowlist: list[str] = Field(
        default_factory=list, description="Allowed version paths"
    )
    deny_patterns: list[str] = Field(
        default_factory=lambda: [
            r"/_sources/",
            r"\.rst\.txt$",
            r"/genindex\.html$",
            r"/py-modindex\.html$",
            r"/search\.html$",
            r"/searchindex\.js$",
            r"/_modules/",
        ],
        description="URL patterns to skip for docs sites",
    )


class DrupalSpiderSettings(BaseModel):
    """Drupal spider settings."""

    deny_patterns: list[str] = Field(
        default_factory=lambda: [r"/node/\d+"],
        description="URL patterns to skip for Drupal sites",
    )


class GenericSpiderSettings(BaseModel):
    """Generic spider settings."""

    deny_patterns: list[str] = Field(
        default_factory=list,
        description="URL patterns to skip",
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
        default_factory=list, description="URLs to start crawling from"
    )
    languages: list[str] = Field(
        default_factory=list,
        description="Restrict language detection to these languages",
    )
    allowed_domains: list[str] = Field(
        default_factory=list, description="Additional allowed domains (regex patterns)"
    )
    forbidden_domains: list[str] = Field(
        default_factory=list,
        description="Domains to exclude even if they match allowed_domains (regex patterns)",
    )
    output: Path = Field(Path("output"), description="Output directory")
    max_depth: int = Field(100, description="Maximum crawl depth")
    delay: float = Field(1.0, description="Delay between requests in seconds")
    concurrent: int = Field(5, description="Maximum concurrent requests")
    verbose: int = Field(0, description="Verbosity level (0=INFO, 1+=DEBUG)")
    proxy: ProxyConfig | None = Field(None, description="Proxy configuration")
    domain_routing: DomainRouting = Field(
        default_factory=DomainRouting, description="Domain to spider routing"
    )
    spider_settings: SpiderSettings = Field(
        default_factory=SpiderSettings, description="Spider-specific settings"
    )
    es_state_host: str | None = Field(
        None,
        description="Elasticsearch host for state tracking (enables stateful mode)",
    )
    es_state_index: str = Field(
        "harmony-crawl-state", description="Elasticsearch index name for crawl state"
    )
    jobdir: Path | None = Field(None, description="Directory for pause/resume state")
    recrawl_mode: RecrawlMode = Field(
        "full", description="Re-crawl mode (full or age-based)"
    )
    max_age_days: int = Field(
        30, description="Max age in days for age-based re-crawling"
    )
    delete_missing: bool = Field(
        default=False,
        description="Automatically delete URLs missing for threshold crawls",
    )
    missing_threshold: int = Field(
        3, description="Number of crawls before marking URL for deletion"
    )
    safe_mode: bool = Field(
        default=False,
        description="Enable extra strict safety checks",
    )
    dry_run: bool = Field(
        default=False,
        description="Dry run mode (log URLs but don't request)",
    )
    allow_mutations: bool = Field(
        default=False,
        description="Allow mutation endpoints (edit, update, delete) - USE WITH CAUTION",
    )
    ignore_robots: bool = Field(
        default=False,
        description="Ignore robots.txt (not recommended)",
    )
    safety_allow_list: list[str] = Field(
        default_factory=list,
        description="Regex patterns for URLs to allow (bypasses safety checks)",
    )
    safety_deny_list: list[str] = Field(
        default_factory=list,
        description="Additional regex patterns for URLs to block",
    )
    safety_lists_file: Path = Field(
        default=Path(".harmony-safety-lists.json"),
        description="File to persist learned allow/deny patterns",
    )
    link_extractor_deny: list[str] = Field(
        default_factory=list,
        description="Regex patterns for URLs to skip (scope filtering, not safety)",
    )
    interactive_safety: bool = Field(
        default=False,
        description="Prompt user to approve/deny blocked URLs interactively",
    )
    autothrottle_enabled: bool = Field(
        default=True,
        description="Enable AutoThrottle for adaptive request throttling",
    )
    autothrottle_start_delay: float = Field(
        default=1.0,
        description="Initial download delay for AutoThrottle (seconds)",
    )
    autothrottle_max_delay: float = Field(
        default=10.0,
        description="Maximum download delay for AutoThrottle (seconds)",
    )
    download_timeout: float = Field(
        default=180.0,
        description="Request timeout in seconds",
    )
    auth: AuthConfig | None = Field(
        None,
        description="Authentication configuration for protected sites",
    )

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
    ) -> DocsSpiderSettings | DrupalSpiderSettings | GenericSpiderSettings | dict[str, typing.Any] | None:
        """Get settings for a specific spider."""
        if spider_name == "docs":
            return self.spider_settings.docs
        if spider_name == "drupal":
            return self.spider_settings.drupal
        if spider_name == "generic":
            return self.spider_settings.generic
        return None
