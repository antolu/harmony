from __future__ import annotations

import logging
from pathlib import Path

import scrapy.logformatter
from rich.logging import RichHandler
from twisted.internet.error import DNSLookupError
from twisted.python.failure import Failure

logger = logging.getLogger("harmony")


class HarmonyLogFormatter(scrapy.logformatter.LogFormatter):
    """Custom log formatter to suppress noisy tracebacks."""

    def download_error(
        self,
        failure: Failure,
        request: scrapy.Request,
        spider: scrapy.Spider,
        errmsg: str | None = None,
    ) -> scrapy.logformatter.LogFormatterResult:
        # Suppress tracebacks for DNS errors
        if failure.check(DNSLookupError):
            return {
                "level": logging.WARNING,
                "msg": f"DNS lookup failed for {request.url}, skipping.",
                "args": {},
            }
        return super().download_error(failure, request, spider, errmsg)


class DropItemFilter(logging.Filter):
    """Filter out Scrapy's 'Dropped:' log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not (
            record.levelno == logging.WARNING and "Dropped:" in record.getMessage()
        )


def setup_logging(*, verbosity: int = 0, log_file: Path | None = None) -> None:
    """Setup logging with verbosity levels.

    Args:
        verbosity: 0=INFO (default), 1+=DEBUG
        log_file: Optional file path for logging
    """
    level = logging.INFO if verbosity == 0 else logging.DEBUG

    handlers: list[logging.Handler] = [RichHandler(rich_tracebacks=True)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    for handler in handlers:
        handler.setLevel(level)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers,
        force=True,
    )

    # Ensure harmony loggers use the configured level
    logging.getLogger("harmony").setLevel(level)
    logging.getLogger("scrapy").setLevel(level)

    # Suppress noisy Elasticsearch logs (only show WARNING+)
    logging.getLogger("elastic_transport").setLevel(logging.WARNING)

    # Filter out Scrapy's dropped item warnings
    scrapy_scraper = logging.getLogger("scrapy.core.scraper")
    scrapy_scraper.addFilter(DropItemFilter())
