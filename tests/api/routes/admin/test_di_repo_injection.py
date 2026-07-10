from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from harmony.api._dependencies import (
    get_auth_sessions_repo,
    get_current_user,
    get_safety_lists_repo,
)
from harmony.api.main import app
from harmony.models import UserIdentity


def _admin_user() -> UserIdentity:
    return UserIdentity(
        id="u1",
        sub="u1",
        email="a@b.com",
        display_name="A",
        harmony_role="admin",
    )


def test_get_safety_lists_uses_injected_repo(mock_app_state: None) -> None:
    repo = MagicMock()
    repo.load_all = AsyncMock(return_value=(["allow1"], ["deny1"]))
    app.dependency_overrides[get_safety_lists_repo] = lambda: repo
    app.dependency_overrides[get_current_user] = _admin_user
    try:
        resp = TestClient(app).get("/api/internal/safety-lists")
    finally:
        app.dependency_overrides.pop(get_safety_lists_repo, None)
        app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200
    assert resp.json() == {"allow": ["allow1"], "deny": ["deny1"]}


def test_add_safety_pattern_uses_injected_repo(mock_app_state: None) -> None:
    repo = MagicMock()
    repo.add_pattern = AsyncMock()
    app.dependency_overrides[get_safety_lists_repo] = lambda: repo
    app.dependency_overrides[get_current_user] = _admin_user
    try:
        resp = TestClient(app).post(
            "/api/internal/safety-lists",
            json={"pattern": "foo.*", "list_type": "allow"},
        )
    finally:
        app.dependency_overrides.pop(get_safety_lists_repo, None)
        app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 201
    repo.add_pattern.assert_called_once_with("foo.*", "allow")


def test_remove_safety_pattern_uses_injected_repo(mock_app_state: None) -> None:
    repo = MagicMock()
    repo.remove_pattern = AsyncMock()
    app.dependency_overrides[get_safety_lists_repo] = lambda: repo
    app.dependency_overrides[get_current_user] = _admin_user
    try:
        resp = TestClient(app).delete(
            "/api/internal/safety-lists", params={"pattern": "foo.*"}
        )
    finally:
        app.dependency_overrides.pop(get_safety_lists_repo, None)
        app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200
    repo.remove_pattern.assert_called_once_with("foo.*")


def test_publish_safety_decision_always_uses_injected_repo(
    mock_app_state: None,
) -> None:
    repo = MagicMock()
    repo.add_pattern = AsyncMock()
    app.dependency_overrides[get_safety_lists_repo] = lambda: repo
    app.dependency_overrides[get_current_user] = _admin_user
    try:
        resp = TestClient(app).post(
            "/api/internal/safety-decision/job-1",
            json={"pattern": "foo.*", "decision": "always"},
        )
    finally:
        app.dependency_overrides.pop(get_safety_lists_repo, None)
        app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 201
    repo.add_pattern.assert_called_once_with("foo.*", "allow")


def test_get_auth_sessions_uses_injected_repo(mock_app_state: None) -> None:
    repo = MagicMock()
    repo.load_all = AsyncMock(return_value=[])
    app.dependency_overrides[get_auth_sessions_repo] = lambda: repo
    app.dependency_overrides[get_current_user] = _admin_user
    try:
        resp = TestClient(app).get("/api/internal/auth-sessions")
    finally:
        app.dependency_overrides.pop(get_auth_sessions_repo, None)
        app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200
    assert resp.json() == []


def test_upsert_auth_session_uses_injected_repo(mock_app_state: None) -> None:
    repo = MagicMock()
    repo.upsert = AsyncMock()
    app.dependency_overrides[get_auth_sessions_repo] = lambda: repo
    app.dependency_overrides[get_current_user] = _admin_user
    try:
        resp = TestClient(app).post(
            "/api/internal/auth-sessions",
            json={"subdomain": "example.com"},
        )
    finally:
        app.dependency_overrides.pop(get_auth_sessions_repo, None)
        app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 201
    repo.upsert.assert_called_once()


def test_delete_auth_session_uses_injected_repo(mock_app_state: None) -> None:
    repo = MagicMock()
    repo.delete = AsyncMock()
    app.dependency_overrides[get_auth_sessions_repo] = lambda: repo
    app.dependency_overrides[get_current_user] = _admin_user
    try:
        resp = TestClient(app).delete("/api/internal/auth-sessions/example.com")
    finally:
        app.dependency_overrides.pop(get_auth_sessions_repo, None)
        app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200
    repo.delete.assert_called_once_with("example.com")
