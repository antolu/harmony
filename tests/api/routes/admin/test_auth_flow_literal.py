from __future__ import annotations

from fastapi.testclient import TestClient

from harmony.api.main import app


def test_test_connection_rejects_invalid_flow_literal() -> None:
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
    assert resp.status_code == 422


def test_test_connection_accepts_valid_flow_literal() -> None:
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
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
