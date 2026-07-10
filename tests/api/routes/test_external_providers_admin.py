from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from harmony.api._dependencies import get_secret_service, get_service_config_store
from harmony.api.main import app


def _make_service_config(overrides: dict | None = None) -> MagicMock:
    defaults = {
        "external_search_brave_enabled": "false",
        "external_search_google_enabled": "false",
        "brave_api_key": "",
        "google_api_key": "",
        "external_search_brave_limit": "5",
        "external_search_google_limit": "5",
    }
    if overrides:
        defaults.update(overrides)
    config = MagicMock()
    config.get = AsyncMock(side_effect=lambda key: defaults.get(key, ""))
    config.set = AsyncMock()
    config.get_external_search_defaults_for_roles = AsyncMock(return_value={})
    config.set_external_search_default_for_role = AsyncMock()
    return config


def _make_secret_service() -> MagicMock:
    svc = MagicMock()
    svc.encrypt = MagicMock(return_value="ENC:xxx")
    svc.decrypt = MagicMock(return_value="plaintext")
    return svc


def _make_admin_user() -> object:
    from harmony.models import UserIdentity

    return UserIdentity(
        id="admin-user",
        sub="admin-sub",
        email="admin@example.com",
        display_name="Admin",
        harmony_role="admin",
        harmony_roles=["admin"],
    )


def _make_non_admin_user() -> object:
    from harmony.models import UserIdentity

    return UserIdentity(
        id="regular-user",
        sub="regular-sub",
        email="user@example.com",
        display_name="User",
        harmony_role="read_only",
        harmony_roles=["read_only"],
    )


def test_get_external_providers_never_returns_key_value(mock_app_state: None) -> None:
    from harmony.api._dependencies import get_current_user

    config = _make_service_config({"brave_api_key": "ENC:real-encrypted-key"})
    config.get_external_search_defaults_for_roles = AsyncMock(return_value={})

    app.dependency_overrides[get_service_config_store] = lambda: config
    app.dependency_overrides[get_secret_service] = _make_secret_service
    app.dependency_overrides[get_current_user] = _make_admin_user
    try:
        resp = TestClient(app).get("/api/settings/external-providers")
    finally:
        app.dependency_overrides.pop(get_service_config_store, None)
        app.dependency_overrides.pop(get_secret_service, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    body = resp.text
    assert "ENC:real-encrypted-key" not in body
    assert "sk-" not in body

    providers = resp.json()
    brave = next(p for p in providers if p["provider"] == "brave")
    assert brave["has_key"] is True
    assert "key" not in brave


def test_get_external_providers_includes_default_for_roles(
    mock_app_state: None,
) -> None:
    from harmony.api._dependencies import get_current_user

    config = _make_service_config()
    config.get_external_search_defaults_for_roles = AsyncMock(
        return_value={"admin": True, "read_only": False}
    )

    app.dependency_overrides[get_service_config_store] = lambda: config
    app.dependency_overrides[get_secret_service] = _make_secret_service
    app.dependency_overrides[get_current_user] = _make_admin_user
    try:
        resp = TestClient(app).get("/api/settings/external-providers")
    finally:
        app.dependency_overrides.pop(get_service_config_store, None)
        app.dependency_overrides.pop(get_secret_service, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    providers = resp.json()
    brave = next(p for p in providers if p["provider"] == "brave")
    assert brave["default_for_roles"] == {"admin": True, "read_only": False}


def test_get_external_providers_default_for_roles_empty_when_unconfigured(
    mock_app_state: None,
) -> None:
    from harmony.api._dependencies import get_current_user

    config = _make_service_config()
    config.get_external_search_defaults_for_roles = AsyncMock(return_value={})

    app.dependency_overrides[get_service_config_store] = lambda: config
    app.dependency_overrides[get_secret_service] = _make_secret_service
    app.dependency_overrides[get_current_user] = _make_admin_user
    try:
        resp = TestClient(app).get("/api/settings/external-providers")
    finally:
        app.dependency_overrides.pop(get_service_config_store, None)
        app.dependency_overrides.pop(get_secret_service, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    providers = resp.json()
    brave = next(p for p in providers if p["provider"] == "brave")
    assert brave["default_for_roles"] == {}


def test_post_provider_key_stores_encrypted_value(mock_app_state: None) -> None:
    from harmony.api._dependencies import get_current_user

    config = _make_service_config()
    secret_svc = _make_secret_service()

    app.dependency_overrides[get_service_config_store] = lambda: config
    app.dependency_overrides[get_secret_service] = lambda: secret_svc
    app.dependency_overrides[get_current_user] = _make_admin_user
    try:
        resp = TestClient(app).post(
            "/api/settings/external-providers/brave/key",
            json={"key": "my-brave-key"},
        )
    finally:
        app.dependency_overrides.pop(get_service_config_store, None)
        app.dependency_overrides.pop(get_secret_service, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 204
    secret_svc.encrypt.assert_called_once_with("my-brave-key")
    config.set.assert_called_once_with("brave_api_key", "ENC:xxx")


def test_patch_provider_enable_updates_config(mock_app_state: None) -> None:
    from harmony.api._dependencies import get_current_user

    config = _make_service_config()

    app.dependency_overrides[get_service_config_store] = lambda: config
    app.dependency_overrides[get_secret_service] = _make_secret_service
    app.dependency_overrides[get_current_user] = _make_admin_user
    try:
        resp = TestClient(app).patch(
            "/api/settings/external-providers/brave",
            json={"enabled": True},
        )
    finally:
        app.dependency_overrides.pop(get_service_config_store, None)
        app.dependency_overrides.pop(get_secret_service, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 204
    config.set.assert_any_call("external_search_brave_enabled", "true")


def test_patch_provider_default_for_roles_stores_per_role_keys(
    mock_app_state: None,
) -> None:
    from harmony.api._dependencies import get_current_user

    config = _make_service_config()

    app.dependency_overrides[get_service_config_store] = lambda: config
    app.dependency_overrides[get_secret_service] = _make_secret_service
    app.dependency_overrides[get_current_user] = _make_admin_user
    try:
        resp = TestClient(app).patch(
            "/api/settings/external-providers/brave",
            json={"default_for_roles": {"admin": True, "read_only": False}},
        )
    finally:
        app.dependency_overrides.pop(get_service_config_store, None)
        app.dependency_overrides.pop(get_secret_service, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 204
    calls = config.set_external_search_default_for_role.call_args_list
    called_args = {
        (c.args[0], c.kwargs.get("default_on", c.args[1] if len(c.args) > 1 else None))
        for c in calls
    }
    assert ("admin", True) in called_args
    assert ("read_only", False) in called_args


def test_patch_provider_omitting_default_for_roles_does_not_clear_existing(
    mock_app_state: None,
) -> None:
    from harmony.api._dependencies import get_current_user

    config = _make_service_config()

    app.dependency_overrides[get_service_config_store] = lambda: config
    app.dependency_overrides[get_secret_service] = _make_secret_service
    app.dependency_overrides[get_current_user] = _make_admin_user
    try:
        resp = TestClient(app).patch(
            "/api/settings/external-providers/brave",
            json={"enabled": True},
        )
    finally:
        app.dependency_overrides.pop(get_service_config_store, None)
        app.dependency_overrides.pop(get_secret_service, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 204
    config.set_external_search_default_for_role.assert_not_called()


def test_routes_require_admin_role(mock_app_state: None) -> None:
    from harmony.api._dependencies import get_current_user
    from harmony.models import AnonymousIdentity

    config = _make_service_config()

    app.dependency_overrides[get_service_config_store] = lambda: config
    app.dependency_overrides[get_secret_service] = _make_secret_service
    app.dependency_overrides[get_current_user] = AnonymousIdentity
    try:
        resp_get = TestClient(app).get("/api/settings/external-providers")
        resp_post = TestClient(app).post(
            "/api/settings/external-providers/brave/key", json={"key": "x"}
        )
        resp_patch = TestClient(app).patch(
            "/api/settings/external-providers/brave", json={"enabled": True}
        )
    finally:
        app.dependency_overrides.pop(get_service_config_store, None)
        app.dependency_overrides.pop(get_secret_service, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp_get.status_code == 403
    assert resp_post.status_code == 403
    assert resp_patch.status_code == 403
