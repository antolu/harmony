from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from harmony.api.dependencies import get_auth_sessions_repo, get_current_user
from harmony.api.main import app
from harmony.api.models.user import UserIdentity


def _admin_user() -> UserIdentity:
    return UserIdentity(
        id="u1",
        sub="u1",
        email="a@b.com",
        display_name="A",
        harmony_role="admin",
    )


def test_get_auth_sessions_serializes_datetime_fields(mock_app_state: None) -> None:
    repo = MagicMock()
    created = datetime(2026, 1, 1, tzinfo=UTC)
    expires = datetime(2026, 1, 2, tzinfo=UTC)
    repo.load_all = AsyncMock(
        return_value=[
            {
                "subdomain": "my-oidc",
                "provider_type": "oidc",
                "created_at": created.isoformat(),
                "expires_at": expires.isoformat(),
            }
        ]
    )
    app.dependency_overrides[get_auth_sessions_repo] = lambda: repo
    app.dependency_overrides[get_current_user] = _admin_user
    try:
        resp = TestClient(app).get("/api/internal/auth-sessions")
    finally:
        app.dependency_overrides.pop(get_auth_sessions_repo, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["created_at"] == created.isoformat()
    assert body[0]["expires_at"] == expires.isoformat()
