from __future__ import annotations

import secrets
import typing
import uuid

import psycopg_pool


class AuthSessionData(typing.TypedDict, total=False):
    subdomain: str
    provider_type: str
    domain_pattern: str
    cookies: dict[str, str]
    headers: dict[str, str]
    storage_state_file: str | None
    created_at: typing.Any
    expires_at: typing.Any


class JobData(typing.TypedDict):
    id: str
    type: str
    status: str
    config_name: str
    started_at: str | None
    finished_at: str | None
    pid: int | None
    log_file: str | None
    error: str | None


class JobProgressData(typing.TypedDict, total=False):
    pages_crawled: int
    pages_pending: int
    requests_made: int
    pages_per_min: float
    current_url: str | None
    documents_indexed: int
    total_documents: int
    current_phase: str | None
    timestamp: str | None


class ServiceConfigData(typing.TypedDict):
    key: str
    value: str
    description: str
    is_configured: bool
    validated_at: str | None
    updated_at: str | None


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

    async def load_all(self) -> list[AuthSessionData]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT subdomain, provider_type, domain_pattern, cookies, headers, "
                "storage_state_file, created_at, expires_at FROM auth_sessions"
            )
            columns = [desc[0] for desc in cur.description]
            return [
                typing.cast(AuthSessionData, dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]

    async def upsert(self, subdomain: str, data: AuthSessionData) -> None:
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

    async def load_all(self) -> list[JobData]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT * FROM jobs ORDER BY started_at DESC")
            columns = [desc[0] for desc in cur.description]
            return [
                typing.cast(JobData, dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]

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

    async def update_progress(self, job_id: str, progress: JobProgressData) -> None:
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
                    progress.get("pages_crawled", 0),
                    progress.get("pages_pending", 0),
                    progress.get("requests_made", 0),
                    progress.get("pages_per_min", 0.0),
                    progress.get("current_url"),
                    progress.get("documents_indexed", 0),
                    progress.get("total_documents", 0),
                    progress.get("current_phase"),
                    progress.get("timestamp"),
                    job_id,
                ),
            )


class ServiceConfigRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def get(self, key: str) -> ServiceConfigData | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT key, value, description, is_configured, validated_at, updated_at FROM service_configs WHERE key = %s",
                (key,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return {
                "key": row[0],
                "value": row[1],
                "description": row[2],
                "is_configured": row[3],
                "validated_at": row[4],
                "updated_at": row[5],
            }

    async def get_all(self) -> list[ServiceConfigData]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT key, value, description, is_configured, validated_at, updated_at FROM service_configs"
            )
            columns = [
                "key",
                "value",
                "description",
                "is_configured",
                "validated_at",
                "updated_at",
            ]
            return [
                typing.cast(ServiceConfigData, dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]

    async def upsert(
        self,
        key: str,
        value: str,
        description: str | None = None,
        *,
        validated: bool = True,
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                INSERT INTO service_configs (key, value, description, is_configured, validated_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    description = EXCLUDED.description,
                    is_configured = EXCLUDED.is_configured,
                    validated_at = CASE WHEN EXCLUDED.is_configured THEN CURRENT_TIMESTAMP ELSE service_configs.validated_at END,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value, description, validated),
            )

    async def is_configured(self) -> bool:
        """Check if all required services are configured."""
        required_services = 2  # elasticsearch_url and redis_url
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM service_configs
                WHERE key IN ('elasticsearch_url', 'redis_url')
                AND is_configured = true
                """
            )
            row = await cur.fetchone()
            return row[0] == required_services if row else False


class UserData(typing.TypedDict, total=False):
    id: str
    sub: str
    email: str | None
    display_name: str | None
    harmony_role: str
    created_at: str
    last_login_at: str | None


class UsersRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def get_by_sub(self, sub: str) -> UserData | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, sub, email, display_name, harmony_role, created_at, last_login_at "
                "FROM users WHERE sub = %s",
                (sub,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "sub": row[1],
                "email": row[2],
                "display_name": row[3],
                "harmony_role": row[4],
                "created_at": str(row[5]),
                "last_login_at": str(row[6]) if row[6] is not None else None,
            }

    async def get_by_id(self, user_id: str) -> UserData | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, sub, email, display_name, harmony_role, created_at, last_login_at "
                "FROM users WHERE id = %s",
                (user_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "sub": row[1],
                "email": row[2],
                "display_name": row[3],
                "harmony_role": row[4],
                "created_at": str(row[5]),
                "last_login_at": str(row[6]) if row[6] is not None else None,
            }

    async def upsert(
        self,
        sub: str,
        email: str | None = None,
        display_name: str | None = None,
        harmony_role: str = "read_only",
    ) -> UserData:
        new_id = str(uuid.uuid4())
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO users (id, sub, email, display_name, harmony_role)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (sub) DO UPDATE SET
                        email = COALESCE(EXCLUDED.email, users.email),
                        display_name = COALESCE(EXCLUDED.display_name, users.display_name),
                        harmony_role = COALESCE(NULLIF(EXCLUDED.harmony_role, 'read_only'), users.harmony_role),
                        last_login_at = now()
                    RETURNING id, sub, email, display_name, harmony_role, created_at, last_login_at
                    """,
                    (new_id, sub, email, display_name, harmony_role),
                )
                row = await cur.fetchone()
        if not row:
            msg = f"Upsert for sub={sub!r} returned no rows"
            raise RuntimeError(msg)
        return {
            "id": row[0],
            "sub": row[1],
            "email": row[2],
            "display_name": row[3],
            "harmony_role": row[4],
            "created_at": str(row[5]),
            "last_login_at": str(row[6]) if row[6] is not None else None,
        }

    async def update_role(self, user_id: str, role: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "UPDATE users SET harmony_role = %s WHERE id = %s",
                (role, user_id),
            )


class ApiKeyData(typing.TypedDict):
    key: str
    description: str
    created_at: str
    revoked_at: str | None


class ApiKeysRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def validate(self, key: str) -> bool:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT revoked_at FROM api_keys WHERE key = %s",
                (key,),
            )
            row = await cur.fetchone()
            if not row:
                return False
            return row[0] is None

    async def create(self, description: str = "") -> str:
        key = secrets.token_urlsafe(32)
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "INSERT INTO api_keys (key, description, created_at) VALUES (%s, %s, now())",
                (key, description),
            )
        return key
