from __future__ import annotations

import json
import secrets
import typing
import uuid

import psycopg_pool

from harmony.api.models.registry import ModelType


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


class AuditEventRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def record(
        self,
        user_id: str,
        action: str,
        entity_type: str,
        entity_id: str | None,
        details: dict[str, typing.Any],
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "INSERT INTO audit_events (user_id, action, entity_type, entity_id, details, created_at) "
                "VALUES (%s, %s, %s, %s, %s, now())",
                (user_id, action, entity_type, entity_id, json.dumps(details)),
            )

    async def query(
        self,
        user_id: str | None,
        action: str | None,
        days_back: int,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, typing.Any]], int]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM audit_events ae
                WHERE ae.created_at > now() - interval '1 day' * %s
                  AND (%s::text IS NULL OR ae.user_id = %s)
                  AND (%s::text IS NULL OR ae.action = %s)
                """,
                (days_back, user_id, user_id, action, action),
            )
            total: int = (await cur.fetchone())[0]  # type: ignore[index]
            await cur.execute(
                """
                SELECT ae.id, ae.user_id, COALESCE(u.email, ae.user_id) AS user_email,
                       ae.action, ae.entity_type, ae.entity_id, ae.details, ae.created_at
                FROM audit_events ae
                LEFT JOIN users u ON u.id::text = ae.user_id
                WHERE ae.created_at > now() - interval '1 day' * %s
                  AND (%s::text IS NULL OR ae.user_id = %s)
                  AND (%s::text IS NULL OR ae.action = %s)
                ORDER BY ae.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (days_back, user_id, user_id, action, action, limit, offset),
            )
            columns = [desc.name for desc in cur.description]
            events = [
                typing.cast(
                    dict[str, typing.Any], dict(zip(columns, row, strict=False))
                )
                for row in await cur.fetchall()
            ]
            return events, total

    async def cleanup(self, retention_days: int) -> int:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM audit_events WHERE created_at < now() - interval '1 day' * %s",
                    (retention_days,),
                )
                return cur.rowcount


class SearchQueryLogRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def record(  # noqa: PLR0913
        self,
        user_id: str,
        query: str,
        language: str | None,
        result_count: int | None,
        latency_ms: int | None,
        tokens: int | None,
        mode: str | None,
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "INSERT INTO search_query_log (user_id, query, language, result_count, latency_ms, tokens, mode, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, now())",
                (user_id, query, language, result_count, latency_ms, tokens, mode),
            )


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
    ) -> list[dict[str, typing.Any]]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, job_id, level, message, created_at FROM job_logs "
                "WHERE job_id = %s ORDER BY created_at ASC LIMIT %s OFFSET %s",
                (job_id, limit, offset),
            )
            columns = ["id", "job_id", "level", "message", "created_at"]
            return [
                typing.cast(
                    dict[str, typing.Any], dict(zip(columns, row, strict=False))
                )
                for row in await cur.fetchall()
            ]


class CrawlBlacklistRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def list(self) -> list[dict[str, typing.Any]]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT cb.id, cb.pattern, cb.reason,
                       COALESCE(u.display_name, u.email, cb.created_by::text) AS created_by,
                       cb.created_at
                FROM crawl_blacklist cb
                LEFT JOIN users u ON u.id = cb.created_by::uuid
                ORDER BY cb.created_at DESC
                """
            )
            columns = ["id", "pattern", "reason", "created_by", "created_at"]
            return [
                typing.cast(
                    dict[str, typing.Any], dict(zip(columns, row, strict=False))
                )
                for row in await cur.fetchall()
            ]

    async def add(
        self, pattern: str, reason: str | None, created_by: str
    ) -> dict[str, typing.Any]:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO crawl_blacklist (pattern, reason, created_by, created_at) "
                    "VALUES (%s, %s, %s, now()) RETURNING id, pattern, reason, created_by, created_at",
                    (pattern, reason, created_by),
                )
                row = await cur.fetchone()
        if not row:
            msg = "Insert for crawl_blacklist returned no rows"
            raise RuntimeError(msg)
        columns = ["id", "pattern", "reason", "created_by", "created_at"]
        return typing.cast(dict[str, typing.Any], dict(zip(columns, row, strict=False)))

    async def remove(self, pattern_id: str) -> bool:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM crawl_blacklist WHERE id = %s",
                    (pattern_id,),
                )
                return cur.rowcount > 0

    async def get_patterns(self) -> list[str]:  # type: ignore[valid-type]
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT pattern FROM crawl_blacklist")
            return [row[0] for row in await cur.fetchall()]


class WebhookRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def list(self) -> list[dict[str, typing.Any]]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, url, events, enabled, created_by, created_at FROM webhooks ORDER BY created_at DESC"
            )
            columns = ["id", "url", "events", "enabled", "created_by", "created_at"]
            return [
                typing.cast(
                    dict[str, typing.Any], dict(zip(columns, row, strict=False))
                )
                for row in await cur.fetchall()
            ]

    async def get(self, webhook_id: str) -> dict[str, typing.Any] | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, url, events, enabled, secret_encrypted, created_by, created_at FROM webhooks WHERE id = %s",
                (webhook_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            columns = [
                "id",
                "url",
                "events",
                "enabled",
                "secret_encrypted",
                "created_by",
                "created_at",
            ]
            return typing.cast(
                dict[str, typing.Any], dict(zip(columns, row, strict=False))
            )

    async def create(
        self,
        url: str,
        secret_encrypted: str | None,
        events: list[str],  # type: ignore[valid-type]
        created_by: str,
    ) -> dict[str, typing.Any]:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO webhooks (url, secret_encrypted, events, enabled, created_by)
                    VALUES (%s, %s, %s, true, %s)
                    RETURNING id, url, events, enabled, secret_encrypted, created_by, created_at
                    """,
                    (url, secret_encrypted, json.dumps(events), created_by),
                )
                row = await cur.fetchone()
        if not row:
            msg = "Insert for webhook returned no rows"
            raise RuntimeError(msg)
        columns = [
            "id",
            "url",
            "events",
            "enabled",
            "secret_encrypted",
            "created_by",
            "created_at",
        ]
        return typing.cast(dict[str, typing.Any], dict(zip(columns, row, strict=False)))

    async def delete(self, webhook_id: str) -> bool:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM webhooks WHERE id = %s", (webhook_id,))
                return cur.rowcount > 0

    async def get_for_event(self, event: str) -> list[dict[str, typing.Any]]:  # type: ignore[valid-type]
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, url, events, enabled, secret_encrypted, created_by, created_at FROM webhooks WHERE enabled = true AND events @> %s::jsonb",
                (json.dumps([event]),),
            )
            columns = [
                "id",
                "url",
                "events",
                "enabled",
                "secret_encrypted",
                "created_by",
                "created_at",
            ]
            return [
                typing.cast(
                    dict[str, typing.Any], dict(zip(columns, row, strict=False))
                )
                for row in await cur.fetchall()
            ]

    async def record_delivery(  # noqa: PLR0913
        self,
        webhook_id: str,
        event: str,
        status: str,
        attempts: int,
        error: str | None,
        delivered_at: typing.Any,
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                INSERT INTO webhook_deliveries (webhook_id, event, status, attempts, last_error, delivered_at, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, now())
                """,
                (webhook_id, event, status, attempts, error, delivered_at),
            )


_ALLOWED_MODEL_UPDATE_COLUMNS = frozenset({
    "name",
    "provider",
    "model_id",
    "model_type",
    "api_key_encrypted",
    "cost_per_token",
    "enabled",
    "ollama_host",
})


class ModelRegistryRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def list_all(self) -> list[dict[str, typing.Any]]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, provider, model_id, model_type, api_key_encrypted, "
                "allowed_groups, cost_per_token, enabled, ollama_host, created_at, updated_at "
                "FROM model_registry ORDER BY model_type, name"
            )
            columns = [desc.name for desc in cur.description]
            return [
                typing.cast(
                    dict[str, typing.Any], dict(zip(columns, row, strict=False))
                )
                for row in await cur.fetchall()
            ]

    async def get(self, model_id_pk: str) -> dict[str, typing.Any] | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM model_registry WHERE id = %s",
                (model_id_pk,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            columns = [desc.name for desc in cur.description]
            return typing.cast(
                dict[str, typing.Any], dict(zip(columns, row, strict=False))
            )

    async def get_by_name(self, name: str) -> dict[str, typing.Any] | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT * FROM model_registry WHERE name = %s",
                (name,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            columns = [desc.name for desc in cur.description]
            return typing.cast(
                dict[str, typing.Any], dict(zip(columns, row, strict=False))
            )

    async def create(  # noqa: PLR0913
        self,
        name: str,
        provider: str,
        model_id: str,
        model_type: ModelType,
        api_key_encrypted: str | None,
        cost_per_token: float | None,
        *,
        enabled: bool,
        ollama_host: str | None,
    ) -> dict[str, typing.Any]:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO model_registry
                        (name, provider, model_id, model_type, api_key_encrypted,
                         cost_per_token, enabled, ollama_host)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, name, provider, model_id, model_type, cost_per_token,
                              enabled, ollama_host, created_at, updated_at
                    """,
                    (
                        name,
                        provider,
                        model_id,
                        model_type,
                        api_key_encrypted,
                        cost_per_token,
                        enabled,
                        ollama_host,
                    ),
                )
                row = await cur.fetchone()
        if not row:
            msg = f"Insert for model_registry name={name!r} returned no rows"
            raise RuntimeError(msg)
        columns = [
            "id",
            "name",
            "provider",
            "model_id",
            "model_type",
            "cost_per_token",
            "enabled",
            "ollama_host",
            "created_at",
            "updated_at",
        ]
        return typing.cast(dict[str, typing.Any], dict(zip(columns, row, strict=False)))

    async def update(
        self, model_pk: str, fields: dict[str, typing.Any]
    ) -> dict[str, typing.Any] | None:
        if not fields:
            return await self.get(model_pk)
        unknown = set(fields) - _ALLOWED_MODEL_UPDATE_COLUMNS
        if unknown:
            msg = f"Unknown update fields: {unknown}"
            raise ValueError(msg)
        set_parts = [f"{k} = %s" for k in fields]
        set_parts.append("updated_at = now()")
        set_clause = ", ".join(set_parts)
        values = list(fields.values())
        values.append(model_pk)
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    f"UPDATE model_registry SET {set_clause} WHERE id = %s "
                    "RETURNING id, name, provider, model_id, model_type, cost_per_token, "
                    "enabled, ollama_host, updated_at",
                    values,
                )
                row = await cur.fetchone()
        if not row:
            return None
        columns = [
            "id",
            "name",
            "provider",
            "model_id",
            "model_type",
            "cost_per_token",
            "enabled",
            "ollama_host",
            "updated_at",
        ]
        return typing.cast(dict[str, typing.Any], dict(zip(columns, row, strict=False)))

    async def delete(self, model_pk: str) -> bool:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM model_registry WHERE id = %s",
                    (model_pk,),
                )
                return cur.rowcount > 0

    async def get_active_by_type(
        self, model_type: ModelType
    ) -> list[dict[str, typing.Any]]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, provider, model_id, model_type, cost_per_token, "
                "enabled, ollama_host, created_at, updated_at "
                "FROM model_registry WHERE model_type = %s AND enabled = true",
                (model_type,),
            )
            columns = [desc.name for desc in cur.description]
            return [
                typing.cast(
                    dict[str, typing.Any], dict(zip(columns, row, strict=False))
                )
                for row in await cur.fetchall()
            ]

    async def count_by_type(self, model_type: ModelType) -> int:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM model_registry WHERE model_type = %s",
                (model_type,),
            )
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def disable_others_of_type(
        self, model_type: ModelType, except_id: str
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE model_registry SET enabled = false, updated_at = now() "
                    "WHERE model_type = %s AND id != %s AND enabled = true",
                    (model_type, except_id),
                )


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


class DataSourceData(typing.TypedDict):
    id: str
    name: str
    provider_type: str
    config: dict[str, typing.Any]
    description: str | None
    created_by: str | None
    created_at: typing.Any
    updated_at: typing.Any
    last_run_at: typing.Any
    last_run_status: str | None
    last_run_doc_count: int | None


_DATA_SOURCE_COLUMNS = (
    "id, name, provider_type, config, description, created_by, "
    "created_at, updated_at, last_run_at, last_run_status, last_run_doc_count"
)


class DataSourcesRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def list_all(self) -> list[DataSourceData]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                f"SELECT {_DATA_SOURCE_COLUMNS} FROM data_sources ORDER BY name"
            )
            columns = [desc.name for desc in cur.description]
            return [
                typing.cast(DataSourceData, dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]

    async def get(self, id: str) -> DataSourceData | None:  # noqa: A002
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                f"SELECT {_DATA_SOURCE_COLUMNS} FROM data_sources WHERE id = %s",
                (id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            columns = [desc.name for desc in cur.description]
            return typing.cast(DataSourceData, dict(zip(columns, row, strict=False)))

    async def create(
        self,
        name: str,
        provider_type: str,
        config_data: dict[str, typing.Any],
        description: str | None,
        created_by: str | None,
    ) -> DataSourceData:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    INSERT INTO data_sources (name, provider_type, config, description, created_by)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING {_DATA_SOURCE_COLUMNS}
                    """,
                    (
                        name,
                        provider_type,
                        json.dumps(config_data),
                        description,
                        created_by,
                    ),
                )
                row = await cur.fetchone()
                columns = [desc.name for desc in cur.description]
        if not row:
            msg = f"Insert for data_source name={name!r} returned no rows"
            raise RuntimeError(msg)
        return typing.cast(DataSourceData, dict(zip(columns, row, strict=False)))

    async def update(
        self,
        id: str,  # noqa: A002
        name: str,
        config_data: dict[str, typing.Any],
        description: str | None,
    ) -> DataSourceData | None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    UPDATE data_sources
                    SET name = %s, config = %s, description = %s, updated_at = now()
                    WHERE id = %s
                    RETURNING {_DATA_SOURCE_COLUMNS}
                    """,
                    (name, json.dumps(config_data), description, id),
                )
                row = await cur.fetchone()
                columns = [desc.name for desc in cur.description]
        if not row:
            return None
        return typing.cast(DataSourceData, dict(zip(columns, row, strict=False)))

    async def delete(self, id: str) -> None:  # noqa: A002
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute("DELETE FROM data_sources WHERE id = %s", (id,))

    async def create_if_not_exists(
        self,
        name: str,
        provider_type: str,
        config_data: dict[str, typing.Any],
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                INSERT INTO data_sources (name, provider_type, config)
                VALUES (%s, %s, %s)
                ON CONFLICT (name) DO NOTHING
                """,
                (name, provider_type, json.dumps(config_data)),
            )

    async def update_last_run(
        self,
        id: str,  # noqa: A002
        status: str,
        doc_count: int | None,
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                UPDATE data_sources
                SET last_run_at = now(), last_run_status = %s, last_run_doc_count = %s
                WHERE id = %s
                """,
                (status, doc_count, id),
            )


class FilesystemStateRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def get_hash(self, data_source_id: str, file_uri: str) -> str | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT content_hash FROM filesystem_state "
                "WHERE data_source_id = %s AND file_uri = %s",
                (data_source_id, file_uri),
            )
            row = await cur.fetchone()
            return row[0] if row else None

    async def upsert(
        self,
        data_source_id: str,
        file_uri: str,
        content_hash: str,
        size_bytes: int | None,
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                """
                INSERT INTO filesystem_state (data_source_id, file_uri, content_hash, size_bytes)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (data_source_id, file_uri) DO UPDATE SET
                    content_hash = EXCLUDED.content_hash,
                    size_bytes = EXCLUDED.size_bytes,
                    indexed_at = now()
                """,
                (data_source_id, file_uri, content_hash, size_bytes),
            )

    async def delete_by_source(self, data_source_id: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "DELETE FROM filesystem_state WHERE data_source_id = %s",
                (data_source_id,),
            )

    async def list_uris(self, data_source_id: str) -> list[str]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT file_uri FROM filesystem_state WHERE data_source_id = %s",
                (data_source_id,),
            )
            return [row[0] for row in await cur.fetchall()]

    async def delete_uris(self, data_source_id: str, file_uris: list[str]) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "DELETE FROM filesystem_state WHERE data_source_id = %s AND file_uri = ANY(%s)",
                (data_source_id, file_uris),
            )
