from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlparse

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from harmony.crawler.config import CrawlerConfig
from harmony.crawler.logger import setup_logging


def main() -> None:
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
