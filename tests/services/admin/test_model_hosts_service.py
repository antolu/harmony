from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from harmony.db.models import ModelHostRow
from harmony.services.admin import ModelHostService


@pytest.fixture
def repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def model_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(repo: MagicMock, model_repo: MagicMock) -> ModelHostService:
    svc = ModelHostService()
    svc._repo = repo
    svc._model_repo = model_repo
    svc._audit_log = AsyncMock()
    return svc


def _host_row(host_id: str = "host-1") -> ModelHostRow:
    now = datetime.datetime.now(tz=datetime.UTC)
    return ModelHostRow(
        id=host_id,
        name="local",
        url="http://x",
        host_type="ollama",
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_create_rejects_invalid_host_type(service: ModelHostService) -> None:
    with pytest.raises(ValueError, match="Invalid host_type"):
        await service.create(
            name="x", url="http://x", host_type="bogus", created_by="user-1"
        )


@pytest.mark.asyncio
async def test_update_rejects_invalid_host_type(service: ModelHostService) -> None:
    with pytest.raises(ValueError, match="Invalid host_type"):
        await service.update("host-1", {"host_type": "bogus"}, updated_by="user-1")


@pytest.mark.asyncio
async def test_delete_blocks_when_models_use_host_and_force_false(
    service: ModelHostService, repo: MagicMock, model_repo: MagicMock
) -> None:
    repo.delete = AsyncMock()
    model_repo.count_models_using_host = AsyncMock(return_value=2)

    result = await service.delete("host-1", force=False, deleted_by="user-1")

    assert result.blocked is True
    assert result.model_count == 2
    repo.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_disables_models_and_deletes_when_forced(
    service: ModelHostService, repo: MagicMock, model_repo: MagicMock
) -> None:
    repo.delete = AsyncMock()
    model_repo.count_models_using_host = AsyncMock(return_value=2)
    model_repo.disable_models_using_host = AsyncMock()

    result = await service.delete("host-1", force=True, deleted_by="user-1")

    assert result.blocked is False
    assert result.model_count == 2
    model_repo.disable_models_using_host.assert_awaited_once_with("host-1")
    repo.delete.assert_awaited_once_with("host-1")


@pytest.mark.asyncio
async def test_delete_proceeds_without_force_when_no_models_use_host(
    service: ModelHostService, repo: MagicMock, model_repo: MagicMock
) -> None:
    repo.delete = AsyncMock()
    model_repo.count_models_using_host = AsyncMock(return_value=0)

    result = await service.delete("host-1", force=False, deleted_by="user-1")

    assert result.blocked is False
    repo.delete.assert_awaited_once_with("host-1")


@pytest.mark.asyncio
async def test_list_all_annotates_model_count_per_host(
    service: ModelHostService, repo: MagicMock, model_repo: MagicMock
) -> None:
    repo.list_all = AsyncMock(return_value=[_host_row("host-1")])
    model_repo.count_models_by_host = AsyncMock(return_value={"host-1": 5})

    result = await service.list_all()

    assert result[0].model_count == 5


@pytest.mark.asyncio
async def test_list_all_defaults_model_count_to_zero_when_unused(
    service: ModelHostService, repo: MagicMock, model_repo: MagicMock
) -> None:
    repo.list_all = AsyncMock(return_value=[_host_row("host-1")])
    model_repo.count_models_by_host = AsyncMock(return_value={})

    result = await service.list_all()

    assert result[0].model_count == 0
