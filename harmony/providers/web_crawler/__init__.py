from __future__ import annotations

from harmony._mod_replace import replace_modname
from harmony.providers.web_crawler.auth import (
    AuthConfig,
    AuthMiddleware,
    AuthProviderConfig,
    AuthProviderRegistry,
    AuthSession,
)
from harmony.providers.web_crawler.auth.config import OIDCAuthConfig
from harmony.providers.web_crawler.auth.providers.oidc import OIDCAuth
from harmony.providers.web_crawler.cli_crawl import main as cli_crawl_main
from harmony.providers.web_crawler.cli_index import main as cli_index_main
from harmony.providers.web_crawler.runtime.config import CrawlerConfig
from harmony.providers.web_crawler.runtime.items import DocumentItem, PageItem
from harmony.providers.web_crawler.runtime.safety import SafetyConfig, is_url_safe
from harmony.providers.web_crawler.runtime.safety_lists import SafetyListsManager
from harmony.providers.web_crawler.runtime.spiders.harmony import HarmonySpider
from harmony.providers.web_crawler.runtime.state import CrawlStateManager

replace_modname(AuthConfig, __name__)
replace_modname(AuthMiddleware, __name__)
replace_modname(AuthProviderRegistry, __name__)
replace_modname(AuthSession, __name__)
replace_modname(CrawlStateManager, __name__)
replace_modname(CrawlerConfig, __name__)
replace_modname(DocumentItem, __name__)
replace_modname(HarmonySpider, __name__)
replace_modname(OIDCAuth, __name__)
replace_modname(OIDCAuthConfig, __name__)
replace_modname(PageItem, __name__)
replace_modname(SafetyConfig, __name__)
replace_modname(SafetyListsManager, __name__)
replace_modname(cli_crawl_main, __name__)
replace_modname(cli_index_main, __name__)
replace_modname(is_url_safe, __name__)

__all__ = [
    "AuthConfig",
    "AuthMiddleware",
    "AuthProviderConfig",
    "AuthProviderRegistry",
    "AuthSession",
    "CrawlStateManager",
    "CrawlerConfig",
    "DocumentItem",
    "HarmonySpider",
    "OIDCAuth",
    "OIDCAuthConfig",
    "PageItem",
    "SafetyConfig",
    "SafetyListsManager",
    "cli_crawl_main",
    "cli_index_main",
    "is_url_safe",
]
