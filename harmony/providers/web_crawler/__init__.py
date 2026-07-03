from __future__ import annotations

from harmony._mod_replace import replace_modname

from .auth import (
    AuthConfig,
    AuthMiddleware,
    AuthProviderConfig,
    AuthProviderRegistry,
    AuthSession,
    OIDCAuthConfig,
)
from .auth.providers import OIDCAuth
from .cli_crawl import main as cli_crawl_main
from .cli_index import main as cli_index_main
from .runtime import (
    CrawlerConfig,
    CrawlStateManager,
    DocumentItem,
    HarmonySpider,
    PageItem,
    SafetyConfig,
    SafetyListsManager,
    is_url_safe,
)

replace_modname(AuthConfig, __name__)
replace_modname(AuthMiddleware, __name__)
replace_modname(AuthProviderRegistry, __name__)
replace_modname(AuthSession, __name__)
replace_modname(CrawlStateManager, __name__)
replace_modname(CrawlerConfig, __name__)
replace_modname(DocumentItem, __name__)
# This rewrite of HarmonySpider.__module__ is why SPIDER_MODULES in
# runtime/settings.py must point at this package rather than
# runtime.spiders directly -- see the comment there.
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
