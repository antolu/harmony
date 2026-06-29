from __future__ import annotations

import asyncio
import typing

from harmony.db.connection import get_async_pool
from harmony.db.repositories import JobLogsRepo

if typing.TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class LogStreamer:
    """Streams job log lines from Postgres so any replica can serve any job's logs.

    Log lines are persisted to the job_logs table by JobLogStreamManager as the
    job runs, so reads do not require a shared filesystem (D-07).
    """

    async def _repo(self) -> JobLogsRepo:
        pool = await get_async_pool()
        return JobLogsRepo(pool)

    async def tail_log(self, job_id: str, num_lines: int = 100) -> list[str]:
        """Return the last N log lines for a job."""
        repo = await self._repo()
        logs = await repo.get_logs(job_id, limit=num_lines)
        return [entry.message for entry in logs]

    async def stream_log(
        self,
        job_id: str,
        *,
        follow: bool = True,
    ) -> AsyncGenerator[str, None]:
        """Stream a job's log lines, optionally following new lines as they land."""
        repo = await self._repo()
        offset = 0
        while True:
            logs = await repo.get_logs(job_id, limit=1000, offset=offset)
            for entry in logs:
                yield entry.message
            offset += len(logs)

            if not follow:
                break

            await asyncio.sleep(0.5)


log_streamer = LogStreamer()
