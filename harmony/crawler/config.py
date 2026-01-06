from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


class CrawlerConfig:
    """Load and manage crawler configuration from YAML."""

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path
        self.config: dict[str, Any] = {}

        if config_path and config_path.exists():
            with config_path.open() as f:
                self.config = yaml.safe_load(f) or {}

    @property
    def start_urls(self) -> list[str]:
        """Get start URLs from config."""
        return self.config.get("start_urls", [])

    @property
    def domain_routing(self) -> dict[str, Any]:
        """Get domain routing configuration."""
        return self.config.get("domain_routing", {})

    @property
    def default_spider(self) -> str:
        """Get default spider name."""
        return self.domain_routing.get("default", "generic")

    @property
    def spider_settings(self) -> dict[str, dict[str, Any]]:
        """Get spider-specific settings."""
        return self.config.get("spider_settings", {})

    def get_spider_for_domain(self, domain: str) -> str:
        """
        Determine which spider to use for a given domain.

        Priority:
        1. Exact match
        2. Pattern match (in order)
        3. Default spider
        """
        routing = self.domain_routing

        # Check exact matches first
        exact_matches = routing.get("exact", {})
        if domain in exact_matches:
            return exact_matches[domain]

        # Check pattern matches in order
        patterns = routing.get("patterns", [])
        for pattern_config in patterns:
            pattern = pattern_config.get("pattern", "")
            spider = pattern_config.get("spider", "")
            if pattern and spider and re.search(pattern, domain):
                return spider

        # Fall back to default
        return self.default_spider

    def get_spider_settings_for(self, spider_name: str) -> dict[str, Any]:
        """Get settings for a specific spider."""
        return self.spider_settings.get(spider_name, {})
