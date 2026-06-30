from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from harmony.api.dependencies import get_current_user
from harmony.api.main import app
from harmony.api.models.user import AnonymousIdentity, UserIdentity


def _admin_user() -> UserIdentity:
    return UserIdentity(
        id="admin-user",
        sub="admin-sub",
        email="admin@example.com",
        display_name="Admin",
        harmony_role="admin",
        harmony_roles=["admin"],
    )


def _read_only_user() -> UserIdentity:
    return UserIdentity(
        id="ro-user",
        sub="ro-sub",
        email="ro@example.com",
        display_name="RO",
        harmony_role="read_only",
        harmony_roles=["read_only"],
    )


@pytest.fixture
def service() -> Iterator[MagicMock]:
    svc = MagicMock()
    app.state.llm_api_key_service = svc
    yield svc
    del app.state.llm_api_key_service


@pytest.fixture
def as_admin() -> Iterator[None]:
    app.dependency_overrides[get_current_user] = _admin_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def as_read_only() -> Iterator[None]:
    app.dependency_overrides[get_current_user] = _read_only_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def as_anonymous() -> Iterator[None]:
    app.dependency_overrides[get_current_user] = AnonymousIdentity
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client(mock_app_state: None) -> TestClient:
    return TestClient(app)


def test_create_llm_api_key_passes_created_by_from_current_user(
    service: MagicMock, as_admin: None, client: TestClient
) -> None:
    service.create = AsyncMock(
        return_value={
            "id": "key-1",
            "name": "my-key",
            "value_encrypted": None,
            "value_set": True,
            "model_count": 0,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
    )

    resp = client.post(
        "/api/admin/llm-api-keys", json={"name": "my-key", "value": "sk-secret"}
    )

    assert resp.status_code == 200
    service.create.assert_awaited_once_with(
        name="my-key", value="sk-secret", created_by="admin-user"
    )
    assert "value" not in resp.json()


def test_create_llm_api_key_returns_400_on_value_error(
    service: MagicMock, as_admin: None, client: TestClient
) -> None:
    service.create = AsyncMock(side_effect=ValueError("duplicate name"))

    resp = client.post("/api/admin/llm-api-keys", json={"name": "dup", "value": "x"})

    assert resp.status_code == 400


def test_update_llm_api_key_returns_404_when_missing(
    service: MagicMock, as_admin: None, client: TestClient
) -> None:
    service.update = AsyncMock(return_value=None)

    resp = client.put("/api/admin/llm-api-keys/missing-id", json={"name": "renamed"})

    assert resp.status_code == 404


def test_delete_llm_api_key_returns_model_count(
    service: MagicMock, as_admin: None, client: TestClient
) -> None:
    result = MagicMock(blocked=False, model_count=4)
    service.delete = AsyncMock(return_value=result)

    resp = client.delete("/api/admin/llm-api-keys/key-1")

    assert resp.status_code == 200
    assert resp.json() == {"deleted": True, "model_count": 4}
    service.delete.assert_awaited_once_with("key-1", deleted_by="admin-user")


def test_llm_api_key_routes_require_admin_role_for_writes(
    service: MagicMock, as_anonymous: None, client: TestClient
) -> None:
    resp_post = client.post("/api/admin/llm-api-keys", json={"name": "x", "value": "y"})
    resp_put = client.put("/api/admin/llm-api-keys/key-1", json={})
    resp_delete = client.delete("/api/admin/llm-api-keys/key-1")

    assert resp_post.status_code == 403
    assert resp_put.status_code == 403
    assert resp_delete.status_code == 403


def test_list_llm_api_keys_allows_read_only_role(
    service: MagicMock, as_read_only: None, client: TestClient
) -> None:
    service.list_all = AsyncMock(return_value=[])

    resp = client.get("/api/admin/llm-api-keys")

    assert resp.status_code == 200
    assert resp.json() == []
