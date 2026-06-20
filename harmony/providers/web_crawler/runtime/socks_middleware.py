"""SOCKS proxy middleware for Scrapy using PySocks."""

from __future__ import annotations

import socket
import typing
from urllib.parse import urlparse

import socks  # type: ignore[import-untyped]  # PySocks has no stubs
from scrapy import signals
from scrapy.exceptions import NotConfigured

if typing.TYPE_CHECKING:
    from scrapy.crawler import Crawler
    from scrapy.http import Request
    from scrapy.spiders import Spider


class SocksProxyMiddleware:
    """Middleware to route requests through a SOCKS proxy using PySocks."""

    def __init__(self, proxy_url: str) -> None:
        """Initialize SOCKS proxy middleware.

        Args:
            proxy_url: SOCKS proxy URL (e.g., socks5://127.0.0.1:1080)
        """
        parsed = urlparse(proxy_url)

        if parsed.scheme == "socks4":
            proxy_type = socks.SOCKS4
        elif parsed.scheme == "socks5":
            proxy_type = socks.SOCKS5
        else:
            msg = f"Unsupported SOCKS proxy type: {parsed.scheme}"
            raise ValueError(msg)

        self.proxy_type = proxy_type
        self.proxy_host = parsed.hostname
        self.proxy_port = parsed.port or 1080
        self.proxy_username = parsed.username
        self.proxy_password = parsed.password

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> SocksProxyMiddleware:
        """Create middleware from crawler settings."""
        proxy_url = crawler.settings.get("SOCKS_PROXY")
        if not proxy_url:
            msg = "SOCKS_PROXY not configured"
            raise NotConfigured(msg)

        middleware = cls(proxy_url)
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        return middleware

    def spider_opened(self, spider: Spider) -> None:
        """Configure socket to use SOCKS proxy when spider opens."""
        socks.set_default_proxy(
            self.proxy_type,
            self.proxy_host,
            self.proxy_port,
            username=self.proxy_username,
            password=self.proxy_password,
        )
        socket.socket = socks.socksocket  # type: ignore[misc]  # PySocks monkeypatching pattern
        spider.logger.info(
            f"SOCKS proxy enabled: {self.proxy_type} {self.proxy_host}:{self.proxy_port}"
        )

    def process_request(self, request: Request, spider: Spider) -> None:
        """Process request through SOCKS proxy."""
        return
