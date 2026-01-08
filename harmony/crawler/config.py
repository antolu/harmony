from __future__ import annotations

import re
import typing
from pathlib import Path

from pydantic import BaseModel, Field

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


class SpiderSettings(BaseModel):
    """Spider-specific settings."""

    docs: DocsSpiderSettings = Field(
        default_factory=DocsSpiderSettings, description="Documentation spider settings"
    )


class CrawlerConfig(BaseModel):
    """Crawler configuration loaded from YAML or CLI."""

    start_urls: list[str] = Field(
        default_factory=list, description="URLs to start crawling from"
    )
    allowed_domains: list[str] = Field(
        default_factory=list, description="Additional allowed domains"
    )
    output: Path = Field(Path("output"), description="Output directory")
    max_depth: int = Field(100, description="Maximum crawl depth")
    delay: float = Field(1.0, description="Delay between requests in seconds")
    concurrent: int = Field(5, description="Maximum concurrent requests")
    verbose: int = Field(0, description="Verbosity level (0-3)")
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

    def get_spider_settings_for(self, spider_name: str) -> typing.Any:
        """Get settings for a specific spider."""
        if spider_name == "docs":
            return self.spider_settings.docs
        return None
