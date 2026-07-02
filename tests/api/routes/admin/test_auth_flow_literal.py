from __future__ import annotations

from fastapi.testclient import TestClient

from harmony.api._dependencies import get_current_user
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


def test_test_connection_rejects_invalid_flow_literal(mock_app_state: None) -> None:
    app.dependency_overrides[get_current_user] = _admin_user
    try:
        resp = TestClient(app).post(
            "/api/auth/providers/test",
            json={
                "name": "my-oidc",
                "type": "oidc",
                "domains": [r".*\.example\.com"],
                "issuer_url": "https://auth.example.com/realms/test",
                "client_id": "harmony",
                "flow": "not-a-real-flow",
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 422


def test_test_connection_accepts_valid_flow_literal(mock_app_state: None) -> None:
    app.dependency_overrides[get_current_user] = _admin_user
    try:
        resp = TestClient(app).post(
            "/api/auth/providers/test",
            json={
                "name": "my-oidc",
                "type": "oidc",
                "domains": [r".*\.example\.com"],
                "issuer_url": "https://auth.invalid-domain-for-test.example/realms/test",
                "client_id": "harmony",
                "flow": "client_credentials",
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
