from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from jsonargparse import ArgumentParser
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from harmony.crawler.config import CrawlerConfig
from harmony.crawler.logger import logger, setup_logging
from harmony.crawler.safety import SafetyConfig
from harmony.crawler.safety_lists import SafetyListsManager
from harmony.crawler.state import CrawlStateManager


def _get_log_level(verbosity: int) -> str:
    """Convert verbosity level to logging level."""
    if verbosity == 0:
        return "INFO"
    return "DEBUG"


def _setup_state_manager(config: CrawlerConfig) -> CrawlStateManager | None:
    """Initialize state manager if enabled."""
    if not config.es_state_host:
        logger.info("State tracking disabled (stateless mode)")
        return None

    state_manager = CrawlStateManager(
        es_host=config.es_state_host,
        index_name=config.es_state_index,
    )
    logger.info(f"State tracking enabled: {config.es_state_host}")

    if config.recrawl_mode == "age-based":
        stale_urls = state_manager.get_stale_urls(config.max_age_days)
        if stale_urls:
            logger.info(f"Found {len(stale_urls)} stale URLs for re-crawling")
            config.start_urls.extend(stale_urls)

    return state_manager


def _setup_safety_lists(config: CrawlerConfig) -> SafetyListsManager | None:
    """Initialize safety lists manager."""
    if not config.safety_lists_file and not config.interactive_safety:
        return None

    lists_manager = SafetyListsManager(config.safety_lists_file)

    for pattern in config.safety_allow_list:
        lists_manager.add_allow_pattern(pattern)
    for pattern in config.safety_deny_list:
        lists_manager.add_deny_pattern(pattern)

    return lists_manager


def _setup_safety_config(
    config: CrawlerConfig, lists_manager: SafetyListsManager | None
) -> SafetyConfig | None:
    """Create safety configuration if needed."""
    has_safety_config = (
        config.safe_mode
        or config.dry_run
        or config.allow_mutations
        or bool(lists_manager)
        or bool(config.safety_allow_list)
        or bool(config.safety_deny_list)
    )

    if not has_safety_config:
        return None

    safety_config = SafetyConfig(
        safe_mode=config.safe_mode,
        dry_run=config.dry_run,
        allow_list_patterns=config.safety_allow_list,
        additional_deny_patterns=config.safety_deny_list,
    )

    if config.allow_mutations:
        safety_config.dangerous_url_patterns = [
            r"/logout",
            r"/signout",
            r"/sign-out",
        ]

    return safety_config


def _setup_proxy(config: CrawlerConfig, settings: dict) -> None:
    """Configure proxy settings."""
    if not config.proxy:
        return

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


def _configure_scrapy_settings(
    config: CrawlerConfig,
    log_level: str,
    state_manager: CrawlStateManager | None,
    safety_config: SafetyConfig | None,
    lists_manager: SafetyListsManager | None,
) -> dict:
    """Configure Scrapy settings."""
    settings = get_project_settings()
    settings.update({
        "OUTPUT_DIR": str(config.output),
        "DEPTH_LIMIT": config.max_depth,
        "DOWNLOAD_DELAY": config.delay,
        "CONCURRENT_REQUESTS": config.concurrent,
        "CRAWLER_CONFIG": config,
        "STATE_MANAGER": state_manager,
        "DELETE_MISSING": config.delete_missing,
        "MISSING_THRESHOLD": config.missing_threshold,
        "LOG_LEVEL": log_level,
        "LOG_ENABLED": False,
        "LOG_ENCODING": "utf-8",
        "ROBOTSTXT_OBEY": not config.ignore_robots,
        "SAFETY_CONFIG": safety_config,
        "SAFETY_LISTS_MANAGER": lists_manager,
        "INTERACTIVE_SAFETY": config.interactive_safety,
        "DOWNLOADER_MIDDLEWARES": {
            "harmony.crawler.middlewares.SafetyMiddleware": 100,
            "harmony.crawler.middlewares.AllowedDomainsMiddleware": 500,
            "harmony.crawler.middlewares.DeltaFetchMiddleware": 544,
            "harmony.crawler.middlewares.DomainRouterMiddleware": 543,
        },
    })

    if config.jobdir:
        config.jobdir.mkdir(parents=True, exist_ok=True)
        settings.update({"JOBDIR": str(config.jobdir)})
        logger.info(f"Pause/resume enabled: {config.jobdir}")

    _setup_proxy(config, settings)
    return settings


def main() -> None:
    parser = ArgumentParser(
        prog="harmony-crawl",
        description="Harmony web crawler",
    )
    parser.add_argument("--config", type=Path, help="Path to YAML configuration file")
    parser.add_class_arguments(CrawlerConfig, "crawler")
    parser.add_argument(
        "-v",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv, -vvv)",
    )
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

    # Override verbose with -v flag if provided
    if args.v > 0:
        config.verbose = args.v

    if not config.start_urls:
        parser.error("No start URLs provided. Use --crawler.start_urls or config file.")

    config.output.mkdir(parents=True, exist_ok=True)

    log_level = _get_log_level(config.verbose)
    setup_logging(verbosity=config.verbose, log_file=config.output / "crawler.log")

    state_manager = _setup_state_manager(config)
    lists_manager = _setup_safety_lists(config)
    safety_config = _setup_safety_config(config, lists_manager)

    settings = _configure_scrapy_settings(
        config, log_level, state_manager, safety_config, lists_manager
    )

    # Build allowed domain patterns: extract from start_urls + add configured patterns
    allowed_domain_patterns = [
        re.escape(urlparse(url).netloc) for url in config.start_urls
    ]
    if config.allowed_domains:
        # Add user-specified regex patterns
        allowed_domain_patterns.extend(config.allowed_domains)

    # Add patterns to settings for AllowedDomainsMiddleware
    settings["ALLOWED_DOMAIN_PATTERNS"] = allowed_domain_patterns

    process = CrawlerProcess(settings)

    process.crawl(
        "harmony",
        start_urls=config.start_urls,
    )

    process.start()


if __name__ == "__main__":
    main()
