from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from harmony.api.services.admin import ServiceConfigStore
from harmony.db.repositories import ApiKeysRepo, UsersRepo


def _make_pool() -> tuple[Any, Any, Any]:
    cursor = AsyncMock()

    cursor_cm = MagicMock()
    cursor_cm.__aenter__ = AsyncMock(return_value=cursor)
    cursor_cm.__aexit__ = AsyncMock(return_value=False)

    conn = MagicMock()
    conn.cursor.return_value = cursor_cm
    conn.set_autocommit = AsyncMock()
    conn.execute = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)

    conn_cm = MagicMock()
    conn_cm.__aenter__ = AsyncMock(return_value=conn)
    conn_cm.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.connection.return_value = conn_cm

    return pool, conn, cursor


async def test_users_repo_get_by_sub_returns_none_when_not_found() -> None:
    pool, _conn, cursor = _make_pool()
    cursor.fetchone = AsyncMock(return_value=None)
    repo = UsersRepo(pool)
    result = await repo.get_by_sub("nonexistent-sub")
    assert result is None


async def test_users_repo_get_by_sub_returns_user_data() -> None:
    pool, _conn, cursor = _make_pool()
    cursor.fetchone = AsyncMock(
        return_value=(
            "some-uuid",
            "sub-value",
            "user@example.com",
            "Display Name",
            "read_only",
            "2026-01-01T00:00:00Z",
            None,
        )
    )
    repo = UsersRepo(pool)
    result = await repo.get_by_sub("sub-value")
    assert result is not None
    assert result["sub"] == "sub-value"
    assert result["email"] == "user@example.com"
    assert result["harmony_role"] == "read_only"


async def test_users_repo_get_by_id_returns_none_when_not_found() -> None:
    pool, _conn, cursor = _make_pool()
    cursor.fetchone = AsyncMock(return_value=None)
    repo = UsersRepo(pool)
    result = await repo.get_by_id("nonexistent-id")
    assert result is None


async def test_users_repo_upsert_returns_user_data() -> None:
    pool, conn, cursor = _make_pool()
    cursor.fetchone = AsyncMock(
        return_value=(
            "new-uuid",
            "sub-value",
            "user@example.com",
            "Display Name",
            "read_only",
            "2026-01-01T00:00:00Z",
            None,
        )
    )
    conn.set_autocommit = AsyncMock()
    repo = UsersRepo(pool)
    result = await repo.upsert("sub-value", "user@example.com", "Display Name")
    assert result is not None
    assert result["id"] == "new-uuid"
    assert result["sub"] == "sub-value"


async def test_users_repo_upsert_updates_last_login_on_second_call() -> None:
    pool, conn, cursor = _make_pool()
    cursor.fetchone = AsyncMock(
        return_value=(
            "some-uuid",
            "sub-value",
            "user@example.com",
            "Display Name",
            "read_only",
            "2026-01-01T00:00:00Z",
            "2026-05-21T00:00:00Z",
        )
    )
    conn.set_autocommit = AsyncMock()
    repo = UsersRepo(pool)
    result = await repo.upsert("sub-value")
    assert result["last_login_at"] is not None


async def test_users_repo_update_role_executes_update() -> None:
    pool, conn, _cursor = _make_pool()
    conn.set_autocommit = AsyncMock()
    conn.execute = AsyncMock()
    repo = UsersRepo(pool)
    await repo.update_role("some-uuid", "admin")
    conn.execute.assert_called_once()
    call_args = conn.execute.call_args
    assert "harmony_role" in call_args[0][0]


async def test_api_keys_repo_validate_returns_true_for_valid_key() -> None:
    pool, _conn, cursor = _make_pool()
    cursor.fetchone = AsyncMock(return_value=(None,))
    repo = ApiKeysRepo(pool)
    result = await repo.validate("valid-key")
    assert result is True


async def test_api_keys_repo_validate_returns_false_for_revoked_key() -> None:
    pool, _conn, cursor = _make_pool()
    cursor.fetchone = AsyncMock(return_value=("2026-01-01T00:00:00Z",))
    repo = ApiKeysRepo(pool)
    result = await repo.validate("revoked-key")
    assert result is False


async def test_api_keys_repo_validate_returns_false_when_not_found() -> None:
    pool, _conn, cursor = _make_pool()
    cursor.fetchone = AsyncMock(return_value=None)
    repo = ApiKeysRepo(pool)
    result = await repo.validate("nonexistent-key")
    assert result is False


async def test_api_keys_repo_create_returns_url_safe_string() -> None:
    pool, conn, _cursor = _make_pool()
    conn.set_autocommit = AsyncMock()
    conn.execute = AsyncMock()
    repo = ApiKeysRepo(pool)
    key = await repo.create("test description")
    assert isinstance(key, str)
    assert len(key) > 0


def test_service_config_store_has_auth_mode_key() -> None:
    store = ServiceConfigStore()
    assert "auth_mode" in store.DEFAULTS
    assert store.DEFAULTS["auth_mode"] == "optional"


def test_service_config_store_has_oidc_keys() -> None:
    store = ServiceConfigStore()
    for key in [
        "oidc_issuer_url",
        "oidc_client_id",
        "oidc_client_secret",
        "oidc_scopes",
        "oidc_role_claim_key",
        "oidc_role_mapping",
    ]:
        assert key in store.DEFAULTS, f"Missing key: {key}"


def test_service_config_store_has_jwt_keys() -> None:
    store = ServiceConfigStore()
    assert "jwt_private_key_pem" in store.DEFAULTS
    assert "jwt_public_key_pem" in store.DEFAULTS


def test_service_config_store_env_map_has_auth_mode() -> None:
    store = ServiceConfigStore()
    assert "AUTH_MODE" in store._ENV_MAP.values()


async def test_service_config_store_returns_optional_for_auth_mode_default() -> None:
    store = ServiceConfigStore()
    store._repo = None
    result = await store.get("auth_mode")
    assert result == "optional"


async def test_service_config_store_returns_empty_for_oidc_issuer_url_default() -> None:
    store = ServiceConfigStore()
    store._repo = None
    result = await store.get("oidc_issuer_url")
    assert not result
