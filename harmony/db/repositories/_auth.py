from __future__ import annotations

import secrets
import typing
import uuid

import psycopg_pool

from harmony.core import SessionData

from ..models import UserData


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
            return UserData(
                id=row[0],
                sub=row[1],
                email=row[2],
                display_name=row[3],
                harmony_role=row[4],
                created_at=str(row[5]),
                last_login_at=str(row[6]) if row[6] is not None else None,
            )

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
            return UserData(
                id=row[0],
                sub=row[1],
                email=row[2],
                display_name=row[3],
                harmony_role=row[4],
                created_at=str(row[5]),
                last_login_at=str(row[6]) if row[6] is not None else None,
            )

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
        return UserData(
            id=row[0],
            sub=row[1],
            email=row[2],
            display_name=row[3],
            harmony_role=row[4],
            created_at=str(row[5]),
            last_login_at=str(row[6]) if row[6] is not None else None,
        )

    async def update_role(self, user_id: str, role: str) -> None:
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            await conn.execute(
                "UPDATE users SET harmony_role = %s WHERE id = %s",
                (role, user_id),
            )


class AuthSessionsRepo:
    def __init__(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._pool = pool

    async def load_all(self) -> list[SessionData]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT subdomain, provider_type, domain_pattern, cookies, headers, "
                "storage_state_file, created_at, expires_at FROM auth_sessions"
            )
            columns = [desc[0] for desc in (cur.description or [])]
            return [
                typing.cast(SessionData, dict(zip(columns, row, strict=False)))
                for row in await cur.fetchall()
            ]

    async def upsert(self, subdomain: str, data: SessionData) -> None:
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
