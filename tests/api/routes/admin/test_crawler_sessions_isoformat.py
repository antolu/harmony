from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from harmony.api.dependencies import get_auth_sessions_repo
from harmony.api.main import app


def test_get_auth_sessions_serializes_datetime_fields() -> None:
    repo = MagicMock()
    created = datetime(2026, 1, 1, tzinfo=UTC)
    expires = datetime(2026, 1, 2, tzinfo=UTC)
    repo.load_all = AsyncMock(
        return_value=[
            {
                "subdomain": "my-oidc",
                "provider_type": "oidc",
                "created_at": created,
                "expires_at": expires,
            }
        ]
    )
    app.dependency_overrides[get_auth_sessions_repo] = lambda: repo
    try:
        resp = TestClient(app).get("/api/internal/auth-sessions")
    finally:
        app.dependency_overrides.pop(get_auth_sessions_repo, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["created_at"] == created.isoformat()
    assert body[0]["expires_at"] == expires.isoformat()
