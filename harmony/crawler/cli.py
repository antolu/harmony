from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from jsonargparse import ArgumentParser
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from harmony.crawler.config import CrawlerConfig
from harmony.crawler.logger import logger, setup_logging


def main() -> None:  # noqa: PLR0915, PLR0912
    parser = ArgumentParser(
        prog="harmony-crawl",
        description="Harmony web crawler",
    )
    parser.add_argument("--config", type=Path, help="Path to YAML configuration file")
    parser.add_class_arguments(CrawlerConfig, "crawler")
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="Print configuration and exit",
    )

    args = parser.parse_args()

    if args.print_config:
        if args.config:
            cfg = parser.parse_path(args.config)
            args = parser.merge_config(cfg, args)
        print(parser.dump(args, skip_none=False))
        return

    if args.config:
        cfg = parser.parse_path(args.config)
        args = parser.merge_config(cfg, args)

    config: CrawlerConfig = parser.instantiate_classes(args).crawler

    if not config.start_urls:
        parser.error("No start URLs provided. Use --crawler.start_urls or config file.")

    config.output.mkdir(parents=True, exist_ok=True)

    if config.verbose == 0:
        log_level = "WARNING"
    elif config.verbose == 1:
        log_level = "INFO"
    else:
        log_level = "DEBUG"

    settings = get_project_settings()
    settings.update({
        "OUTPUT_DIR": str(config.output),
        "DEPTH_LIMIT": config.max_depth,
        "DOWNLOAD_DELAY": config.delay,
        "CONCURRENT_REQUESTS": config.concurrent,
        "CRAWLER_CONFIG": config,
        "LOG_LEVEL": log_level,
        "LOG_ENABLED": False,
        "LOG_ENCODING": "utf-8",
        "DOWNLOADER_MIDDLEWARES": {
            "harmony.crawler.middlewares.DomainRouterMiddleware": 543,
        },
    })

    if config.proxy:
        proxy_url = config.proxy.url
        proxy_username = config.proxy.username
        proxy_password = config.proxy.password

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

    setup_logging(verbosity=config.verbose, log_file=config.output / "crawler.log")

    process = CrawlerProcess(settings)

    allowed_domains_set = {urlparse(url).netloc for url in config.start_urls}
    if config.allowed_domains:
        for domain in config.allowed_domains:
            if domain.startswith(("http://", "https://")):
                allowed_domains_set.add(urlparse(domain).netloc)
            else:
                allowed_domains_set.add(domain)
    allowed_domains = list(allowed_domains_set)

    process.crawl(
        "harmony",
        start_urls=config.start_urls,
        allowed_domains=allowed_domains,
    )

    process.start()


if __name__ == "__main__":
    main()
