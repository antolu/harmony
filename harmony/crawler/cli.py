from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlparse

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

from harmony.crawler.logger import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Harmony web crawler")
    parser.add_argument(
        "--start-urls", nargs="+", required=True, help="URLs to start crawling from"
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
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)
    setup_logging(verbose=args.verbose, log_file=output_path / "crawler.log")

    settings = get_project_settings()
    settings.update({
        "OUTPUT_DIR": args.output,
        "DEPTH_LIMIT": args.max_depth,
        "DOWNLOAD_DELAY": args.delay,
        "CONCURRENT_REQUESTS": args.concurrent,
    })

    process = CrawlerProcess(settings)

    allowed_domains_set = {urlparse(url).netloc for url in args.start_urls}
    if args.allowed_domains:
        for domain in args.allowed_domains:
            if domain.startswith(("http://", "https://")):
                allowed_domains_set.add(urlparse(domain).netloc)
            else:
                allowed_domains_set.add(domain)
    allowed_domains = list(allowed_domains_set)

    process.crawl(
        "admin_eguide",
        start_urls=args.start_urls,
        allowed_domains=allowed_domains,
    )
    process.start()


if __name__ == "__main__":
    main()
