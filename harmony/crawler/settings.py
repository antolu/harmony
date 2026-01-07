from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

BOT_NAME = "harmony"

SPIDER_MODULES = ["harmony.crawler.spiders"]
NEWSPIDER_MODULE = "harmony.crawler.spiders"

ROBOTSTXT_OBEY = False

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.2 Safari/605.1.15"

CONCURRENT_REQUESTS = 5

DOWNLOAD_DELAY = 1.0

DEPTH_LIMIT = 100

DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cookie": os.getenv("CERN_COOKIE", ""),
    "Connection": "keep-alive",
}

DOWNLOADER_MIDDLEWARES = {
    "harmony.crawler.middlewares.DeltaFetchMiddleware": 544,
    "harmony.crawler.middlewares.DomainRouterMiddleware": 543,
}

ITEM_PIPELINES = {
    "harmony.crawler.pipelines.HTMLExpanderPipeline": 100,
    "harmony.crawler.pipelines.FileStoragePipeline": 200,
    "harmony.crawler.pipelines.DocumentStoragePipeline": 300,
    "harmony.crawler.pipelines.StateUpdatePipeline": 400,
}

EXTENSIONS = {
    "harmony.crawler.extensions.ProgressExtension": 500,
    "harmony.crawler.extensions.DeletionDetectorExtension": 501,
}

TELNETCONSOLE_ENABLED = False

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

LOG_LEVEL = "WARNING"

# Proxy settings (can be overridden by config or CLI)
# HTTP/HTTPS proxy support (built-in Scrapy)
HTTPPROXY_ENABLED = False
HTTPPROXY_AUTH_ENCODING = "utf-8"
