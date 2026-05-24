from __future__ import annotations

import asyncio
import builtins
import contextlib
import fcntl
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import yaml
from jsonargparse import ArgumentParser
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from twisted.internet.defer import TimeoutError as DeferTimeoutError
from twisted.internet.error import (
    ConnectError,
    ConnectionDone,
    ConnectionLost,
)
from twisted.internet.error import (
    ConnectionRefusedError as TwistedConnectionRefusedError,
)
from twisted.internet.error import (
    TimeoutError as ErrorTimeoutError,
)
from twisted.web.client import PartialDownloadError

from harmony.crawler.config import CrawlerConfig
from harmony.crawler.logger import logger, setup_logging
from harmony.crawler.safety import SafetyConfig
from harmony.crawler.safety_lists import SafetyListsManager
from harmony.crawler.state import CrawlStateManager
from harmony.crawler.writers import SafetyListsWriter, make_writers
from harmony.db.connection import get_async_pool
from harmony.db.repositories import ServiceConfigRepo


@dataclass
class CrawlerManagers:
    state_manager: CrawlStateManager | None
    safety_config: SafetyConfig | None
    lists_manager: SafetyListsManager | None
    session_writer: object
    stats_writer: object


def _get_log_level(verbosity: int) -> str:
    """Convert verbosity level to logging level."""
    # Check environment variable first
    env_level = os.environ.get("HARMONY_LOG_LEVEL")
    if env_level:
        return env_level.upper()

    if verbosity == 0:
        return "INFO"
    return "DEBUG"


async def _get_db_config(key: str) -> str | None:
    """Fetch configuration from database."""
    try:
        pool = await get_async_pool()
        repo = ServiceConfigRepo(pool)
        config = await repo.get(key)
        if config and config.get("is_configured"):
            return config["value"]
    except Exception:
        pass
    return None


def _resolve_es_host() -> str | None:
    """Resolve ES state host from Env or DB."""
    # Try environment variable
    env_host = os.environ.get("ES_HOST")
    if env_host:
        return env_host

    # Try database
    db_host = asyncio.run(_get_db_config("elasticsearch_url"))
    if db_host:
        print(f"Using ES config from database: {db_host}")
        return db_host

    return None


def _setup_state_manager(
    config: CrawlerConfig, es_host: str | None
) -> CrawlStateManager | None:
    """Initialize state manager if enabled."""
    if not es_host:
        logger.info("State tracking disabled (stateless mode)")
        return None

    # Use default index name or env override
    index_name = os.environ.get("ES_STATE_INDEX", "harmony-crawl-state")

    state_manager = CrawlStateManager(
        es_host=es_host,
        index_name=index_name,
    )
    logger.info(f"State tracking enabled: {es_host}")

    if config.recrawl_mode == "age-based":
        stale_urls = state_manager.get_stale_urls(config.max_age_days)
        if stale_urls:
            logger.info(f"Found {len(stale_urls)} stale URLs for re-crawling")
            config.start_urls.extend(stale_urls)

    return state_manager


def _setup_safety_lists(
    config: CrawlerConfig, safety_writer: SafetyListsWriter
) -> SafetyListsManager | None:
    """Initialize safety lists manager."""
    lists_manager = SafetyListsManager(safety_writer)

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
    if not config.proxy or not config.proxy.enabled:
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

        # Ensure local services (like Ollama) can be reached without proxy
        no_proxy = os.environ.get("NO_PROXY", "")
        local_hosts = ["localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal"]
        new_no_proxy_parts = [h for h in local_hosts if h not in no_proxy]
        if new_no_proxy_parts:
            separator = "," if no_proxy else ""
            os.environ["NO_PROXY"] = no_proxy + separator + ",".join(new_no_proxy_parts)
    else:
        logger.warning(
            f"Unknown proxy type '{proxy_type}' in URL. Supported: http, https, socks4, socks5"
        )


def _configure_scrapy_settings(
    config: CrawlerConfig,
    log_level: str,
    state_dir: Path,
    managers: CrawlerManagers,
) -> dict:
    """Configure Scrapy settings."""
    settings = get_project_settings()
    settings.update({
        "OUTPUT_DIR": str(config.output),
        "DEPTH_LIMIT": config.max_depth,
        "DOWNLOAD_DELAY": config.delay,
        "CONCURRENT_REQUESTS": config.concurrent,
        "CRAWLER_CONFIG": config,
        "STATE_MANAGER": managers.state_manager,
        "DELETE_MISSING": config.delete_missing,
        "MISSING_THRESHOLD": config.missing_threshold,
        "LOG_LEVEL": log_level,
        "LOG_ENABLED": False,
        "LOG_ENCODING": "utf-8",
        "ROBOTSTXT_OBEY": not config.ignore_robots,
        "SAFETY_CONFIG": managers.safety_config,
        "SAFETY_LISTS_MANAGER": managers.lists_manager,
        "INTERACTIVE_SAFETY": config.interactive_safety,
        "AUTH_CONFIG": config.auth,
        "SESSION_WRITER": managers.session_writer,
        "STATS_WRITER": managers.stats_writer,
        "AUTOTHROTTLE_ENABLED": config.autothrottle.enabled,
        "AUTOTHROTTLE_START_DELAY": config.autothrottle.start_delay,
        "AUTOTHROTTLE_MAX_DELAY": config.autothrottle.max_delay,
        "DOWNLOAD_TIMEOUT": config.download_timeout,
        "DOWNLOADER_MIDDLEWARES": {
            "harmony.crawler.auth.middleware.AuthMiddleware": 50,
            "harmony.crawler.middlewares.AllowedDomainsMiddleware": 85,
            "harmony.crawler.middlewares.SafetyMiddleware": 90,
            "harmony.crawler.middlewares.DeltaFetchMiddleware": 544,
            "harmony.crawler.middlewares.DomainRouterMiddleware": 543,
        },
        "LOG_FORMATTER": "harmony.crawler.logger.HarmonyLogFormatter",
        "RETRY_EXCEPTIONS": [
            DeferTimeoutError,
            ErrorTimeoutError,
            TwistedConnectionRefusedError,
            ConnectionDone,
            ConnectError,
            ConnectionLost,
            PartialDownloadError,
        ],
        "JOBDIR": str(state_dir),
    })

    _setup_proxy(config, settings)
    return settings


def _setup_crawler(
    config: CrawlerConfig,
    managers: CrawlerManagers,
    log_level: str,
    state_dir: Path,
) -> CrawlerProcess:
    """Set up crawler process with domain patterns and configuration."""
    settings = _configure_scrapy_settings(config, log_level, state_dir, managers)

    allowed_domain_patterns = [
        re.escape(urlparse(url).netloc) for url in config.start_urls
    ]
    if config.allowed_domains:
        allowed_domain_patterns.extend(config.allowed_domains)

    settings["ALLOWED_DOMAIN_PATTERNS"] = allowed_domain_patterns
    settings["FORBIDDEN_DOMAIN_PATTERNS"] = config.forbidden_domains

    process = CrawlerProcess(settings)
    process.crawl("harmony", start_urls=config.start_urls)
    return process


def _load_config_file(parser: ArgumentParser, config_path: Path) -> object:
    """Load a YAML config file without expanding dotted dict keys."""
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    autothrottle: dict = raw.setdefault("autothrottle", {})
    for flat, nested in (
        ("autothrottle_enabled", "enabled"),
        ("autothrottle_start_delay", "start_delay"),
        ("autothrottle_max_delay", "max_delay"),
    ):
        if flat in raw:
            autothrottle.setdefault(nested, raw.pop(flat))
    if not autothrottle:
        raw.pop("autothrottle", None)
    known = set(CrawlerConfig.model_fields)
    raw = {k: v for k, v in raw.items() if k in known}
    return parser.parse_object({"crawler": raw})


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

    if args.config:
        cfg = _load_config_file(parser, args.config)
        args = parser.merge_config(cfg, args)

    if args.print_config:
        print(parser.dump(args, skip_none=False))
        return

    config: CrawlerConfig = parser.instantiate_classes(args).crawler

    # Override verbose with -v flag if provided
    if args.v > 0:
        config.verbose = args.v

    if not config.start_urls:
        parser.error("No start URLs provided. Use --crawler.start_urls or config file.")

    config.output.mkdir(parents=True, exist_ok=True)

    log_level = _get_log_level(config.verbose)
    setup_logging(verbosity=config.verbose, log_file=config.output / "crawler.log")

    state_dir = config.output / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)

    safety_writer, session_writer, stats_writer = make_writers(
        config.output, os.environ.get("HARMONY_CRAWL_JOB_ID")
    )

    es_host = _resolve_es_host()
    state_manager = _setup_state_manager(config, es_host)
    lists_manager = _setup_safety_lists(config, safety_writer)
    safety_config = _setup_safety_config(config, lists_manager)

    managers = CrawlerManagers(
        state_manager=state_manager,
        safety_config=safety_config,
        lists_manager=lists_manager,
        session_writer=session_writer,
        stats_writer=stats_writer,
    )

    process = _setup_crawler(config, managers, log_level, state_dir)
    _run_with_lock(process, state_dir)


def _run_with_lock(process: CrawlerProcess, state_dir: Path) -> None:
    lock_file_path = state_dir / "harmony.lock"
    try:
        _run_with_lock_file(process, lock_file_path, state_dir)
    except Exception as e:
        logger.error(f"Error managing lock file: {e}")
        raise


def _run_with_lock_file(
    process: CrawlerProcess, lock_file_path: Path, state_dir: Path
) -> None:
    with open(lock_file_path, "w", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            pass
        except OSError:
            logger.error(
                f"Could not acquire lock on {state_dir}. Is another crawl running?"
            )
            return

        try:
            process.start()
        finally:
            with contextlib.suppress(builtins.BaseException):
                fcntl.flock(lock_file, fcntl.LOCK_UN)


if __name__ == "__main__":
    main()
