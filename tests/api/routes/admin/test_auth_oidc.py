from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi.testclient import TestClient

from harmony.api.dependencies import (
    get_auth_sessions_repo,
    get_config_store,
    get_users_repo,
)
from harmony.api.main import app


def _mock_config_store(flow: str = "client_credentials") -> MagicMock:
    store = MagicMock()
    store.list_configs.return_value = [MagicMock(name="test-crawler")]
    store.get_config.return_value = {
        "auth": {
            "providers": [
                {
                    "name": "my-oidc",
                    "type": "oidc",
                    "domains": [r".*\.example\.com"],
                    "issuer_url": "https://auth.example.com/realms/test",
                    "client_id": "harmony",
                    "client_secret": "secret",
                    "flow": flow,
                }
            ]
        }
    }
    return store


def test_list_providers_includes_oidc() -> None:
    store = _mock_config_store()
    repo = MagicMock()
    repo.load_all = AsyncMock(return_value=[])
    app.dependency_overrides[get_config_store] = lambda: store
    app.dependency_overrides[get_auth_sessions_repo] = lambda: repo
    try:
        resp = TestClient(app).get("/api/auth/providers")
    finally:
        app.dependency_overrides.pop(get_config_store, None)
        app.dependency_overrides.pop(get_auth_sessions_repo, None)
    assert resp.status_code == 200
    providers = resp.json()["providers"]
    assert any(p["name"] == "my-oidc" and p["type"] == "oidc" for p in providers)


def _call_client_credentials_login() -> httpx.Response:
    repo = MagicMock()
    repo.upsert = AsyncMock()
    app.dependency_overrides[get_auth_sessions_repo] = lambda: repo
    try:
        with patch("harmony.api.routes.admin.auth.OIDCAuth") as mock_oidc_cls:
            mock_provider = MagicMock()
            mock_provider.ensure_discovered = AsyncMock()
            mock_provider.authenticate = AsyncMock(
                return_value=MagicMock(
                    headers={"Authorization": "Bearer tok"},
                    created_at=MagicMock(isoformat=lambda: "2026-01-01T00:00:00+00:00"),
                    expires_at=None,
                )
            )
            mock_oidc_cls.return_value = mock_provider
            return TestClient(app).post("/api/auth/login/my-oidc")
    finally:
        app.dependency_overrides.pop(get_auth_sessions_repo, None)


def test_start_login_client_credentials_returns_complete() -> None:
    store = _mock_config_store("client_credentials")
    app.dependency_overrides[get_config_store] = lambda: store
    try:
        resp = _call_client_credentials_login()
    finally:
        app.dependency_overrides.pop(get_config_store, None)
    assert resp.status_code == 200
    assert resp.json()["flow"] == "client_credentials"
    assert resp.json()["complete"] is True


def _call_authorization_code_login() -> httpx.Response:
    repo = MagicMock()
    app.dependency_overrides[get_auth_sessions_repo] = lambda: repo
    try:
        with patch("harmony.api.routes.admin.auth.OIDCAuth") as mock_oidc_cls:
            mock_provider = MagicMock()
            mock_provider.ensure_discovered = AsyncMock()
            mock_provider.build_auth_url = MagicMock(
                return_value=(
                    "https://auth.example.com/auth?foo=bar",
                    "state123",
                    "verifier",
                )
            )
            mock_oidc_cls.return_value = mock_provider
            return TestClient(app).post("/api/auth/login/my-oidc")
    finally:
        app.dependency_overrides.pop(get_auth_sessions_repo, None)


def test_start_login_authorization_code_returns_auth_url() -> None:
    store = _mock_config_store("authorization_code")
    app.dependency_overrides[get_config_store] = lambda: store
    try:
        resp = _call_authorization_code_login()
    finally:
        app.dependency_overrides.pop(get_config_store, None)
    assert resp.status_code == 200
    data = resp.json()
    assert data["flow"] == "authorization_code"
    assert data["auth_url"] is not None
    assert data["complete"] is False


def test_callback_unknown_state_returns_400() -> None:
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    service_config_mock = AsyncMock()
    service_config_mock.get = AsyncMock(return_value="")
    users_repo = MagicMock()
    app.state.redis_client = redis_mock
    app.state.service_config_store = service_config_mock
    app.dependency_overrides[get_users_repo] = lambda: users_repo
    try:
        resp = TestClient(app).get("/api/auth/callback?code=abc&state=unknownstate")
    finally:
        del app.state.redis_client
        del app.state.service_config_store
        app.dependency_overrides.pop(get_users_repo, None)
    assert resp.status_code == 400


def test_test_connection_client_credentials_success() -> None:
    with patch("harmony.api.routes.admin.auth.OIDCAuth") as mock_cls:
        mock_provider = MagicMock()
        mock_provider.ensure_discovered = AsyncMock()
        mock_provider.do_client_credentials = AsyncMock()
        mock_cls.return_value = mock_provider
        resp = TestClient(app).post(
            "/api/auth/providers/test",
            json={
                "name": "my-oidc",
                "type": "oidc",
                "domains": [r".*\.example\.com"],
                "issuer_url": "https://auth.example.com/realms/test",
                "client_id": "harmony",
                "client_secret": "secret",
                "flow": "client_credentials",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
