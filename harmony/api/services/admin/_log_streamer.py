from __future__ import annotations

import asyncio
import typing
from pathlib import Path


class LogStreamer:
    """Service for streaming log file contents."""

    async def tail_log(
        self,
        log_file: Path,
        num_lines: int = 100,
    ) -> list[str]:
        """Read the last N lines from a log file."""
        if not log_file.exists():
            return []

        try:
            lines = log_file.read_text(encoding="utf-8").splitlines()
            return lines[-num_lines:]
        except Exception:
            return []

    async def stream_log(
        self,
        log_file: Path,
        *,
        follow: bool = True,
    ) -> typing.AsyncGenerator[str, None]:
        """Stream log file contents, optionally following new lines."""
        if not log_file.exists():
            return

        position = 0

        while True:
            try:
                with log_file.open("r", encoding="utf-8") as f:
                    f.seek(position)
                    for line in f:
                        yield line.rstrip("\n")
                    position = f.tell()
            except Exception:
                break

            if not follow:
                break

            await asyncio.sleep(0.5)


log_streamer = LogStreamer()
