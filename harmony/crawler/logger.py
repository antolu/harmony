from __future__ import annotations

import logging
from pathlib import Path

from rich.logging import RichHandler

logger = logging.getLogger("harmony")


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
