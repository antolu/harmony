from __future__ import annotations

import json
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

    async def get_harmony_role(self, key: str) -> str | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT harmony_role FROM api_keys WHERE key = %s AND revoked_at IS NULL",
                (key,),
            )
            row = await cur.fetchone()
            return row[0] if row else None


class TokenUsageRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def insert_batch(self, events: list[dict]) -> None:
        if not events:
            return
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.executemany(
                """
                INSERT INTO token_usage
                    (trace_id, user_id, endpoint, agent_step, model, provider,
                     input_tokens, output_tokens, total_tokens, recorded_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        e.get("trace_id"),
                        e.get("user_id"),
                        e.get("endpoint"),
                        e.get("agent_step"),
                        e.get("model", ""),
                        e.get("provider"),
                        e.get("input_tokens"),
                        e.get("output_tokens"),
                        e.get("total_tokens"),
                        e.get("recorded_at"),
                    )
                    for e in events
                ],
            )

    async def query(
        self,
        model: str | None = None,
        user_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        conditions = []
        params: list[typing.Any] = []

        if model:
            conditions.append("model = %s")
            params.append(model)
        if user_id:
            conditions.append("user_id = %s")
            params.append(user_id)
        if date_from:
            conditions.append("recorded_at >= %s")
            params.append(date_from)
        if date_to:
            conditions.append("recorded_at <= %s")
            params.append(date_to)

        # conditions must only contain static string literals; all user values go into params
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        sql = f"""
            SELECT
                user_id,
                model,
                DATE(recorded_at) AS usage_date,
                SUM(input_tokens) AS input_tokens,
                SUM(output_tokens) AS output_tokens,
                SUM(total_tokens) AS total_tokens
            FROM token_usage
            {where}
            GROUP BY user_id, model, DATE(recorded_at)
            ORDER BY usage_date DESC
            LIMIT %s
        """

        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(sql, params)
            columns = [
                "user_id",
                "model",
                "usage_date",
                "input_tokens",
                "output_tokens",
                "total_tokens",
            ]
            return [
                typing.cast(dict, dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]


class MessageFeedbackRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def upsert(
        self, conversation_id: str, message_id: int, user_id: str, rating: str
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                INSERT INTO message_feedback (conversation_id, message_id, user_id, rating)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (conversation_id, message_id, user_id) DO UPDATE SET
                    rating = EXCLUDED.rating,
                    updated_at = now()
                """,
                (conversation_id, message_id, user_id, rating),
            )

    async def get_for_conversation(
        self, conversation_id: str, user_id: str
    ) -> list[dict]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, conversation_id, message_id, user_id, rating, created_at, updated_at
                FROM message_feedback
                WHERE conversation_id = %s AND user_id = %s
                ORDER BY message_id ASC
                """,
                (conversation_id, user_id),
            )
            columns = [desc.name for desc in cur.description]
            return [
                typing.cast(dict, dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]

    async def delete_user_rating(
        self, conversation_id: str, message_id: int, user_id: str
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "DELETE FROM message_feedback WHERE conversation_id = %s AND message_id = %s AND user_id = %s",
                (conversation_id, message_id, user_id),
            )


class ModelPolicyRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def assign_role(self, model_id: str, harmony_role: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "INSERT INTO model_policy (model_id, harmony_role) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (model_id, harmony_role),
            )

    async def remove_role(self, model_id: str, harmony_role: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "DELETE FROM model_policy WHERE model_id = %s AND harmony_role = %s",
                (model_id, harmony_role),
            )

    async def get_allowed_roles(self, model_id: str) -> list[str]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT harmony_role FROM model_policy WHERE model_id = %s",
                (model_id,),
            )
            return [row[0] for row in await cur.fetchall()]

    async def list_all(self) -> list[dict]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT model_id, harmony_role FROM model_policy ORDER BY model_id"
            )
            rows = await cur.fetchall()
        by_model: dict[str, list[str]] = {}
        for model_id, role in rows:
            by_model.setdefault(model_id, []).append(role)
        return [
            {"model_id": mid, "allowed_roles": roles} for mid, roles in by_model.items()
        ]


class CrawlConfigRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def list(self) -> list[dict[str, typing.Any]]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, description, config_json, created_by, created_at, updated_at "
                "FROM crawl_configs ORDER BY name"
            )
            columns = [desc.name for desc in cur.description]
            return [
                typing.cast(
                    dict[str, typing.Any], dict(zip(columns, row, strict=False))
                )
                for row in await cur.fetchall()
            ]

    async def get(self, name: str) -> dict[str, typing.Any] | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, description, config_json, created_by, created_at, updated_at "
                "FROM crawl_configs WHERE name = %s",
                (name,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            columns = [desc.name for desc in cur.description]
            return typing.cast(
                dict[str, typing.Any], dict(zip(columns, row, strict=False))
            )

    async def create(
        self,
        name: str,
        config_json: dict[str, typing.Any],
        description: str | None,
        created_by: str | None,
    ) -> dict[str, typing.Any]:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO crawl_configs (name, config_json, description, created_by)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, name, description, config_json, created_by, created_at, updated_at
                    """,
                    (name, json.dumps(config_json), description, created_by),
                )
                row = await cur.fetchone()
        if not row:
            msg = f"Insert for crawl_config name={name!r} returned no rows"
            raise RuntimeError(msg)
        columns = [
            "id",
            "name",
            "description",
            "config_json",
            "created_by",
            "created_at",
            "updated_at",
        ]
        return typing.cast(dict[str, typing.Any], dict(zip(columns, row, strict=False)))

    async def update(
        self,
        name: str,
        config_json: dict[str, typing.Any],
        description: str | None,
    ) -> dict[str, typing.Any] | None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE crawl_configs
                    SET config_json = %s, description = %s, updated_at = now()
                    WHERE name = %s
                    RETURNING id, name, description, config_json, created_by, created_at, updated_at
                    """,
                    (json.dumps(config_json), description, name),
                )
                row = await cur.fetchone()
        if not row:
            return None
        columns = [
            "id",
            "name",
            "description",
            "config_json",
            "created_by",
            "created_at",
            "updated_at",
        ]
        return typing.cast(dict[str, typing.Any], dict(zip(columns, row, strict=False)))

    async def rename(self, old_name: str, new_name: str) -> bool:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE crawl_configs SET name = %s WHERE name = %s",
                    (new_name, old_name),
                )
                return cur.rowcount > 0

    async def delete(self, name: str) -> bool:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM crawl_configs WHERE name = %s",
                    (name,),
                )
                return cur.rowcount > 0


class IndexerConfigRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def get(self) -> dict[str, typing.Any] | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, config_json, updated_by, updated_at FROM indexer_config LIMIT 1"
            )
            row = await cur.fetchone()
            if not row:
                return None
            columns = [desc.name for desc in cur.description]
            return typing.cast(
                dict[str, typing.Any], dict(zip(columns, row, strict=False))
            )

    async def upsert(
        self,
        config_json: dict[str, typing.Any],
        updated_by: str | None,
    ) -> dict[str, typing.Any]:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM indexer_config")
                await cur.execute(
                    """
                    INSERT INTO indexer_config (config_json, updated_by)
                    VALUES (%s, %s)
                    RETURNING id, config_json, updated_by, updated_at
                    """,
                    (json.dumps(config_json), updated_by),
                )
                row = await cur.fetchone()
        if not row:
            msg = "Insert for indexer_config returned no rows"
            raise RuntimeError(msg)
        columns = ["id", "config_json", "updated_by", "updated_at"]
        return typing.cast(dict[str, typing.Any], dict(zip(columns, row, strict=False)))
