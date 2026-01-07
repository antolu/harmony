from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from harmony.crawler.config import CrawlerConfig
from harmony.crawler.logger import logger, setup_logging


def main() -> None:  # noqa: PLR0915, PLR0914, PLR0912
    parser = argparse.ArgumentParser(description="Harmony web crawler")
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--start-urls",
        nargs="+",
        help="URLs to start crawling from (overrides config file)",
    )
    parser.add_argument(
        "--allowed-domains",
        nargs="+",
        help="Additional domains to allow (can be domains or URLs)",
    )
    parser.add_argument("--output", default="output", help="Output directory")
    parser.add_argument(
        "--max-depth", type=int, default=100, help="Maximum crawl depth"
    )
    parser.add_argument(
        "--delay", type=float, default=1.0, help="Delay between requests in seconds"
    )
    parser.add_argument(
        "--concurrent", type=int, default=5, help="Maximum concurrent requests"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv, -vvv)",
    )

    args = parser.parse_args()

    # Load configuration
    config = CrawlerConfig(args.config)

    # Merge start URLs: config file + CLI args
    start_urls = config.start_urls.copy()
    if args.start_urls:
        start_urls.extend(args.start_urls)

    if not start_urls:
        parser.error("No start URLs provided. Use --start-urls or provide config file.")

    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    # Map verbosity to log levels
    if args.verbose == 0:
        log_level = "WARNING"
    elif args.verbose == 1:
        log_level = "INFO"
    else:
        log_level = "DEBUG"

    settings = get_project_settings()
    settings.update({
        "OUTPUT_DIR": args.output,
        "DEPTH_LIMIT": args.max_depth,
        "DOWNLOAD_DELAY": args.delay,
        "CONCURRENT_REQUESTS": args.concurrent,
        "CRAWLER_CONFIG": config,  # Pass config to middleware
        "LOG_LEVEL": log_level,
        "LOG_ENABLED": False,
        "LOG_ENCODING": "utf-8",
        "DOWNLOADER_MIDDLEWARES": {
            "harmony.crawler.middlewares.DomainRouterMiddleware": 543,
        },
    })

    # Configure proxy if provided in config
    proxy_config = config.proxy
    if proxy_config:
        proxy_url = proxy_config.get("url")
        proxy_username = proxy_config.get("username")
        proxy_password = proxy_config.get("password")

        if not proxy_url:
            logger.warning("Proxy configured but no URL provided. Ignoring proxy.")
        else:
            parsed = urlparse(proxy_url)
            proxy_type = parsed.scheme.lower()

            if proxy_type in {"socks4", "socks5"}:
                settings.update({
                    "DOWNLOADER_MIDDLEWARES": {
                        "harmony.crawler.middlewares.DomainRouterMiddleware": 543,
                        "harmony.crawler.socks_middleware.SocksProxyMiddleware": 542,
                    },
                    "SOCKS_PROXY": proxy_url,
                })
                if proxy_username and proxy_password:
                    logger.info(
                        f"Using {proxy_type.upper()} proxy with authentication: {proxy_url}"
                    )
                else:
                    logger.info(f"Using {proxy_type.upper()} proxy: {proxy_url}")
            elif proxy_type in {"http", "https"}:
                settings.update({
                    "HTTPPROXY_ENABLED": True,
                    "HTTPPROXY_AUTH_ENCODING": "utf-8",
                })
                if proxy_username and proxy_password:
                    proxy_url_with_auth = urlunparse((
                        parsed.scheme,
                        f"{proxy_username}:{proxy_password}@{parsed.netloc}",
                        parsed.path,
                        parsed.params,
                        parsed.query,
                        parsed.fragment,
                    ))
                    os.environ["HTTP_PROXY"] = proxy_url_with_auth
                    os.environ["HTTPS_PROXY"] = proxy_url_with_auth
                    logger.info(
                        f"Using {proxy_type.upper()} proxy with authentication: {parsed.scheme}://{parsed.netloc}"
                    )
                else:
                    os.environ["HTTP_PROXY"] = proxy_url
                    os.environ["HTTPS_PROXY"] = proxy_url
                    logger.info(f"Using {proxy_type.upper()} proxy: {proxy_url}")
            else:
                logger.warning(
                    f"Unknown proxy type '{proxy_type}' in URL. Supported: http, https, socks4, socks5"
                )

    # Setup logging after Scrapy settings are configured
    setup_logging(verbosity=args.verbose, log_file=output_path / "crawler.log")

    process = CrawlerProcess(settings)

    # Collect all allowed domains
    allowed_domains_set = {urlparse(url).netloc for url in start_urls}
    if args.allowed_domains:
        for domain in args.allowed_domains:
            if domain.startswith(("http://", "https://")):
                allowed_domains_set.add(urlparse(domain).netloc)
            else:
                allowed_domains_set.add(domain)
    allowed_domains = list(allowed_domains_set)

    # Start single spider that delegates to processors
    process.crawl(
        "harmony",
        start_urls=start_urls,
        allowed_domains=allowed_domains,
    )

    process.start()


if __name__ == "__main__":
    main()
