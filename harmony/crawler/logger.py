from __future__ import annotations

import logging
from pathlib import Path

from rich.logging import RichHandler


def setup_logging(*, verbose: bool = False, log_file: Path | None = None) -> None:
    level = logging.DEBUG if verbose else logging.INFO

    handlers: list[logging.Handler] = [RichHandler(rich_tracebacks=True)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers,
    )
