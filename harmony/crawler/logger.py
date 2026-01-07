from __future__ import annotations

import logging
from pathlib import Path

from rich.logging import RichHandler

logger = logging.getLogger("harmony")


def setup_logging(*, verbosity: int = 0, log_file: Path | None = None) -> None:
    """Setup logging with verbosity levels.

    Args:
        verbosity: 0=WARNING, 1=INFO, 2=DEBUG, 3+=DEBUG with more detail
        log_file: Optional file path for logging
    """
    if verbosity == 0:
        level = logging.WARNING
    elif verbosity == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG

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
    )
