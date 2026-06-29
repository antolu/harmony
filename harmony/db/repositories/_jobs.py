from __future__ import annotations

import dataclasses
from datetime import datetime

import psycopg_pool

from harmony.api.models.job import JobProgress


@dataclasses.dataclass
class JobData:
    id: str
    type: str
    status: str
    config_name: str
    started_at: str | None
    finished_at: str | None
    pid: int | None
    log_file: str | None
    error: str | None
    progress_pages_crawled: int = 0
    progress_pages_pending: int = 0
    progress_requests_made: int = 0
    progress_pages_per_min: float = 0.0
    progress_current_url: str | None = None
    progress_documents_indexed: int = 0
    progress_total_documents: int = 0
    progress_current_phase: str | None = None
    progress_timestamp: datetime | None = None


class JobsRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def load_all(self) -> list[JobData]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT * FROM jobs ORDER BY started_at DESC")
            columns = [desc[0] for desc in (cur.description or [])]
            return [
                JobData(**dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]

    async def get(self, job_id: str) -> JobData | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
            row = await cur.fetchone()
            if row is None:
                return None
            columns = [desc[0] for desc in (cur.description or [])]
            return JobData(**dict(zip(columns, row, strict=False)))

    async def upsert(self, job: JobData) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                INSERT INTO jobs (id, type, status, config_name, started_at, finished_at, pid, log_file, error)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    started_at = EXCLUDED.started_at,
                    finished_at = EXCLUDED.finished_at,
                    pid = EXCLUDED.pid,
                    log_file = EXCLUDED.log_file,
                    error = EXCLUDED.error
                """,
                (
                    job.id,
                    job.type,
                    job.status,
                    job.config_name,
                    job.started_at,
                    job.finished_at,
                    job.pid,
                    job.log_file,
                    job.error,
                ),
            )

    async def update_status(
        self,
        job_id: str,
        status: str,
        finished_at: datetime | None = None,
        error: str | None = None,
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "UPDATE jobs SET status = %s, finished_at = %s, error = %s WHERE id = %s",
                (status, finished_at, error, job_id),
            )

    async def update_progress(self, job_id: str, progress: JobProgress) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                UPDATE jobs SET
                    progress_pages_crawled = %s,
                    progress_pages_pending = %s,
                    progress_requests_made = %s,
                    progress_pages_per_min = %s,
                    progress_current_url = %s,
                    progress_documents_indexed = %s,
                    progress_total_documents = %s,
                    progress_current_phase = %s,
                    progress_timestamp = %s
                WHERE id = %s
                """,
                (
                    progress.pages_crawled,
                    progress.pages_pending,
                    progress.requests_made,
                    progress.pages_per_min,
                    progress.current_url,
                    progress.documents_indexed,
                    progress.total_documents,
                    progress.current_phase,
                    progress.timestamp,
                    job_id,
                ),
            )


@dataclasses.dataclass
class JobLogData:
    id: str
    job_id: str
    level: str
    message: str
    created_at: datetime


class JobLogsRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def append(self, job_id: str, level: str, message: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "INSERT INTO job_logs (job_id, level, message, created_at) VALUES (%s, %s, %s, now())",
                (job_id, level, message),
            )

    async def get_logs(
        self, job_id: str, limit: int = 1000, offset: int = 0
    ) -> list[JobLogData]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, job_id, level, message, created_at FROM job_logs "
                "WHERE job_id = %s ORDER BY created_at ASC LIMIT %s OFFSET %s",
                (job_id, limit, offset),
            )
            columns = ["id", "job_id", "level", "message", "created_at"]
            return [
                JobLogData(**dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]


class IndexerCheckpointRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def record_indexed(self, config_name: str, url: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "INSERT INTO indexer_checkpoints (config_name, url, indexed_at) VALUES (%s, %s, now()) "
                "ON CONFLICT (config_name, url) DO UPDATE SET indexed_at = now()",
                (config_name, url),
            )

    async def record_indexed_batch(self, config_name: str, urls: list[str]) -> None:
        if not urls:
            return
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.executemany(
                    "INSERT INTO indexer_checkpoints (config_name, url, indexed_at) VALUES (%s, %s, now()) "
                    "ON CONFLICT (config_name, url) DO UPDATE SET indexed_at = now()",
                    [(config_name, url) for url in urls],
                )

    async def get_indexed_urls(self, config_name: str) -> set[str]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT url FROM indexer_checkpoints WHERE config_name = %s",
                (config_name,),
            )
            return {row[0] for row in await cur.fetchall()}

    async def clear(self, config_name: str) -> int:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM indexer_checkpoints WHERE config_name = %s",
                    (config_name,),
                )
                return cur.rowcount
