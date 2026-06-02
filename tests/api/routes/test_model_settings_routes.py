from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from harmony.api.dependencies import get_current_user
from harmony.api.models.user import UserIdentity
from harmony.api.routes.admin.model_settings import router

HTTP_200 = 200
HTTP_204 = 204

_ADMIN_USER = UserIdentity(
    id="test-user",
    sub="test-user",
    harmony_role="admin",
    email="admin@test.com",
    display_name=None,
)


def _make_app(model_registry_service: AsyncMock) -> TestClient:
    test_app = FastAPI()
    test_app.include_router(router, prefix="/admin")
    test_app.dependency_overrides[get_current_user] = lambda: _ADMIN_USER

    state = MagicMock()
    state.model_registry_service = model_registry_service
    test_app.state = state
    return TestClient(test_app)


def test_list_models_returns_models_list() -> None:
    svc = AsyncMock()
    svc.list = AsyncMock(
        return_value=[
            {
                "id": "1",
                "name": "Llama3",
                "provider": "ollama",
                "model_id": "llama3",
                "model_type": "llm",
                "enabled": True,
            }
        ]
    )
    client = _make_app(svc)

    response = client.get("/admin/models")

    assert response.status_code == HTTP_200
    data = response.json()
    assert "models" in data
    assert data["models"][0]["provider"] == "ollama"


def test_create_model_returns_created_entry() -> None:
    svc = AsyncMock()
    svc.create = AsyncMock(
        return_value={
            "id": "2",
            "name": "GPT-4o",
            "provider": "openai",
            "model_id": "gpt-4o",
            "model_type": "llm",
            "enabled": True,
        }
    )
    client = _make_app(svc)

    response = client.post(
        "/admin/models",
        json={
            "name": "GPT-4o",
            "provider": "openai",
            "model_id": "gpt-4o",
            "model_type": "llm",
            "api_key": "sk-test",
        },
    )

    assert response.status_code == HTTP_200
    assert response.json()["provider"] == "openai"


def test_delete_model_returns_204() -> None:
    svc = AsyncMock()
    svc.delete = AsyncMock(return_value=True)
    client = _make_app(svc)

    response = client.delete("/admin/models/1")

    assert response.status_code == HTTP_200
    assert response.json()["deleted"] is True


def test_check_connectivity_returns_result() -> None:
    svc = AsyncMock()
    svc.test_connectivity = AsyncMock(return_value={"ok": True, "latency_ms": 42})
    client = _make_app(svc)

    response = client.post("/admin/models/1/test")

    assert response.status_code == HTTP_200
    assert response.json()["ok"] is True
