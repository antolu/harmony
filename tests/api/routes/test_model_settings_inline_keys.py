from __future__ import annotations

import datetime
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from harmony.api.dependencies import get_current_user
from harmony.api.routes.admin.model_settings import router
from harmony.models import UserIdentity
from harmony.services.admin._models import ModelRegistryRow

_ADMIN_USER = UserIdentity(
    id="test-user",
    sub="test-user",
    harmony_role="admin",
    email="admin@test.com",
    display_name=None,
)


def _model_row(**overrides: object) -> ModelRegistryRow:
    now = datetime.datetime.now(tz=datetime.UTC)
    defaults: dict[str, object] = {
        "id": "1",
        "name": "GPT-4o",
        "provider": "openai",
        "model_id": "gpt-4o",
        "model_type": "llm",
        "api_key_id": None,
        "allowed_groups": [],
        "cost_per_token": None,
        "enabled": True,
        "model_host_id": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return ModelRegistryRow(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def model_registry_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def llm_api_key_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client(
    model_registry_service: AsyncMock, llm_api_key_service: AsyncMock
) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(router, prefix="/admin/models")
    app.dependency_overrides[get_current_user] = lambda: _ADMIN_USER

    state = MagicMock()
    state.model_registry_service = model_registry_service
    state.llm_api_key_service = llm_api_key_service
    app.state = state

    return TestClient(app)


def test_create_model_with_new_api_key_value_creates_key_first(
    client: TestClient,
    model_registry_service: AsyncMock,
    llm_api_key_service: AsyncMock,
) -> None:
    llm_api_key_service.create = AsyncMock(
        return_value=MagicMock(id="generated-key-id")
    )
    model_registry_service.create = AsyncMock(return_value=_model_row())

    response = client.post(
        "/admin/models",
        json={
            "name": "GPT-4o",
            "provider": "openai",
            "model_id": "gpt-4o",
            "model_type": "llm",
            "new_api_key_value": "sk-secret",
            "new_api_key_name": "my-openai-key",
        },
    )

    assert response.status_code == 200
    llm_api_key_service.create.assert_awaited_once_with(
        name="my-openai-key", value="sk-secret", created_by="test-user"
    )
    created_data = model_registry_service.create.call_args.kwargs["data"]
    assert created_data.api_key_id == "generated-key-id"


def test_create_model_with_new_api_key_value_defaults_name_when_omitted(
    client: TestClient,
    model_registry_service: AsyncMock,
    llm_api_key_service: AsyncMock,
) -> None:
    llm_api_key_service.create = AsyncMock(return_value=MagicMock(id="key-id"))
    model_registry_service.create = AsyncMock(return_value=_model_row())

    client.post(
        "/admin/models",
        json={
            "name": "GPT-4o",
            "provider": "openai",
            "model_id": "gpt-4o",
            "model_type": "llm",
            "new_api_key_value": "sk-secret",
        },
    )

    llm_api_key_service.create.assert_awaited_once_with(
        name="Unnamed key", value="sk-secret", created_by="test-user"
    )


def test_create_model_with_existing_api_key_id_skips_key_creation(
    client: TestClient,
    model_registry_service: AsyncMock,
    llm_api_key_service: AsyncMock,
) -> None:
    model_registry_service.create = AsyncMock(return_value=_model_row())

    client.post(
        "/admin/models",
        json={
            "name": "GPT-4o",
            "provider": "openai",
            "model_id": "gpt-4o",
            "model_type": "llm",
            "api_key_id": "existing-key-id",
        },
    )

    llm_api_key_service.create.assert_not_called()
    created_data = model_registry_service.create.call_args.kwargs["data"]
    assert created_data.api_key_id == "existing-key-id"


def test_update_model_with_clear_sentinel_unsets_api_key(
    client: TestClient,
    model_registry_service: AsyncMock,
    llm_api_key_service: AsyncMock,
) -> None:
    model_registry_service.update = AsyncMock(return_value=_model_row())

    client.put("/admin/models/1", json={"api_key_id": "__clear__"})

    llm_api_key_service.create.assert_not_called()
    update_fields = model_registry_service.update.call_args.kwargs["fields"]
    assert update_fields["api_key_id"] is None


def test_update_model_with_new_api_key_value_creates_key_and_sets_id(
    client: TestClient,
    model_registry_service: AsyncMock,
    llm_api_key_service: AsyncMock,
) -> None:
    llm_api_key_service.create = AsyncMock(return_value=MagicMock(id="new-key-id"))
    model_registry_service.update = AsyncMock(return_value=_model_row())

    client.put(
        "/admin/models/1",
        json={"new_api_key_value": "sk-rotated", "new_api_key_name": "rotated-key"},
    )

    llm_api_key_service.create.assert_awaited_once_with(
        name="rotated-key", value="sk-rotated", created_by="test-user"
    )
    update_fields = model_registry_service.update.call_args.kwargs["fields"]
    assert update_fields["api_key_id"] == "new-key-id"
    assert "new_api_key_value" not in update_fields
    assert "new_api_key_name" not in update_fields


def test_validate_model_proxies_to_validate_unsaved_model(
    client: TestClient, model_registry_service: AsyncMock
) -> None:
    model_registry_service.validate_unsaved_model = AsyncMock(
        return_value={"ok": True, "latency_ms": 12.0, "error": None}
    )

    response = client.post(
        "/admin/models/validate",
        json={
            "provider": "ollama",
            "model": "qwen3:8b",
            "model_type": "llm",
            "host_id": "host-1",
            "api_key_id": None,
        },
    )

    assert response.status_code == 200
    model_registry_service.validate_unsaved_model.assert_awaited_once_with(
        provider="ollama",
        model_id="qwen3:8b",
        model_type="llm",
        host_id="host-1",
        api_key_id=None,
    )
    assert response.json()["ok"] is True
