from __future__ import annotations

import os

from dotenv import load_dotenv

from harmony.providers.web_crawler.runtime.safety import SafetyConfig

load_dotenv()

BOT_NAME = "harmony"

SPIDER_MODULES = ["harmony.providers.web_crawler.runtime.spiders"]
NEWSPIDER_MODULE = "harmony.providers.web_crawler.runtime.spiders"

ROBOTSTXT_OBEY = True

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

CONCURRENT_REQUESTS = 5

DOWNLOAD_DELAY = 1.0

DEPTH_LIMIT = 100

DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cookie": os.getenv("CERN_COOKIE", ""),
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

SAFETY_CONFIG = SafetyConfig(
    allowed_methods={"GET", "HEAD"},
    safe_mode=False,
    dry_run=False,
)

DOWNLOADER_MIDDLEWARES = {
    "harmony.providers.web_crawler.auth.middleware.AuthMiddleware": 750,
    "harmony.providers.web_crawler.runtime.middlewares.SafetyMiddleware": 100,
    "harmony.providers.web_crawler.runtime.middlewares.DeltaFetchMiddleware": 544,
    "harmony.providers.web_crawler.runtime.middlewares.DomainRouterMiddleware": 543,
}

ITEM_PIPELINES = {
    "harmony.providers.web_crawler.runtime.pipelines.HTMLExpanderPipeline": 100,
    "harmony.providers.web_crawler.runtime.pipelines.FileStoragePipeline": 200,
    "harmony.providers.web_crawler.runtime.pipelines.DocumentStoragePipeline": 300,
    "harmony.providers.web_crawler.runtime.pipelines.StateUpdatePipeline": 400,
}

EXTENSIONS = {
    "harmony.providers.web_crawler.runtime.extensions.ProgressExtension": 500,
    "harmony.providers.web_crawler.runtime.extensions.DeletionDetectorExtension": 501,
}

TELNETCONSOLE_ENABLED = False

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 10.0

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

LOG_LEVEL = "WARNING"

# Proxy settings (can be overridden by config or CLI)
# HTTP/HTTPS proxy support (built-in Scrapy)
HTTPPROXY_ENABLED = False
HTTPPROXY_AUTH_ENCODING = "utf-8"
