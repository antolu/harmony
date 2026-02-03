from __future__ import annotations

import typing

import psycopg_pool


class SafetyListsRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def load_all(self) -> tuple[list[str], list[str]]:
        allow: list[str] = []
        deny: list[str] = []
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT pattern, list_type FROM safety_lists")
            async for row in cur:
                if row[1] == "allow":
                    allow.append(row[0])
                else:
                    deny.append(row[0])
        return allow, deny

    async def add_pattern(self, pattern: str, list_type: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "INSERT INTO safety_lists (pattern, list_type) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (pattern, list_type),
            )

    async def remove_pattern(self, pattern: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "DELETE FROM safety_lists WHERE pattern = %s", (pattern,)
            )


class AuthSessionsRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def load_all(self) -> list[dict[str, typing.Any]]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT subdomain, provider_type, domain_pattern, cookies, headers, "
                "storage_state_file, created_at, expires_at FROM auth_sessions"
            )
            columns = [desc[0] for desc in cur.description]
            return [
                dict(zip(columns, row, strict=False)) for row in await cur.fetchall()
            ]

    async def upsert(self, subdomain: str, data: dict[str, typing.Any]) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                INSERT INTO auth_sessions
                    (subdomain, provider_type, domain_pattern, cookies, headers, storage_state_file, created_at, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (subdomain) DO UPDATE SET
                    provider_type = EXCLUDED.provider_type,
                    domain_pattern = EXCLUDED.domain_pattern,
                    cookies = EXCLUDED.cookies,
                    headers = EXCLUDED.headers,
                    storage_state_file = EXCLUDED.storage_state_file,
                    expires_at = EXCLUDED.expires_at
                """,
                (
                    subdomain,
                    data.get("provider_type", ""),
                    data.get("domain_pattern", ""),
                    data.get("cookies", {}),
                    data.get("headers", {}),
                    data.get("storage_state_file"),
                    data.get("created_at"),
                    data.get("expires_at"),
                ),
            )

    async def delete(self, subdomain: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "DELETE FROM auth_sessions WHERE subdomain = %s", (subdomain,)
            )

    async def clear_all(self) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute("DELETE FROM auth_sessions")


class JobsRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def load_all(self) -> list[dict[str, typing.Any]]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT * FROM jobs")
            columns = [desc[0] for desc in cur.description]
            return [
                dict(zip(columns, row, strict=False)) for row in await cur.fetchall()
            ]

    async def upsert(self, job: dict[str, typing.Any]) -> None:
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
                    job["id"],
                    job["type"],
                    job["status"],
                    job["config_name"],
                    job.get("started_at"),
                    job.get("finished_at"),
                    job.get("pid"),
                    job.get("log_file"),
                    job.get("error"),
                ),
            )

    async def update_status(
        self,
        job_id: str,
        status: str,
        finished_at: typing.Any = None,
        error: str | None = None,
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "UPDATE jobs SET status = %s, finished_at = %s, error = %s WHERE id = %s",
                (status, finished_at, error, job_id),
            )

    async def update_progress(
        self, job_id: str, progress: dict[str, typing.Any]
    ) -> None:
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
                    progress_timestamp = %s
                WHERE id = %s
                """,
                (
                    progress.get("pages_crawled", 0),
                    progress.get("pages_pending", 0),
                    progress.get("requests_made", 0),
                    progress.get("pages_per_min", 0.0),
                    progress.get("current_url"),
                    progress.get("timestamp"),
                    job_id,
                ),
            )
