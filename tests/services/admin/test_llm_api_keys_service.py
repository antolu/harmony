from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from harmony.services.admin import LLMApiKeyService
from harmony.services.admin._models import LLMApiKeyRow  # noqa: PLC2701


@pytest.fixture
def repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def model_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def secrets() -> MagicMock:
    return MagicMock()


@pytest.fixture
def audit_log() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(
    repo: MagicMock, model_repo: MagicMock, secrets: MagicMock, audit_log: AsyncMock
) -> LLMApiKeyService:
    svc = LLMApiKeyService()
    svc._repo = repo
    svc._model_repo = model_repo
    svc._audit_log = audit_log
    svc._secrets = secrets
    return svc


def _key_row(
    key_id: str = "key-1", value_encrypted: str | None = "ENC:x"
) -> LLMApiKeyRow:
    now = datetime.datetime.now(tz=datetime.UTC)
    return LLMApiKeyRow(
        id=key_id,
        name="my-key",
        value_encrypted=value_encrypted,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_create_encrypts_value_before_storing(
    service: LLMApiKeyService, repo: MagicMock, secrets: MagicMock
) -> None:
    repo.create = AsyncMock(return_value=_key_row())
    secrets.encrypt = MagicMock(return_value="ENC:secret")

    await service.create(name="my-key", value="plaintext", created_by="user-1")

    secrets.encrypt.assert_called_once_with("plaintext")
    create_call = repo.create.call_args.args[0]
    assert create_call.value_encrypted == "ENC:secret"


@pytest.mark.asyncio
async def test_annotate_never_exposes_value_encrypted(
    service: LLMApiKeyService, repo: MagicMock, secrets: MagicMock
) -> None:
    repo.create = AsyncMock(return_value=_key_row(value_encrypted="ENC:secret"))
    secrets.encrypt = MagicMock(return_value="ENC:secret")

    row = await service.create(name="my-key", value="plaintext", created_by="user-1")

    assert row.value_encrypted is None
    assert row.value_set is True


@pytest.mark.asyncio
async def test_list_all_annotates_model_count_per_key(
    service: LLMApiKeyService, repo: MagicMock, model_repo: MagicMock
) -> None:
    repo.list_all = AsyncMock(return_value=[_key_row("key-1")])
    model_repo.count_models_by_key = AsyncMock(return_value={"key-1": 3})

    result = await service.list_all()

    assert result[0].model_count == 3


@pytest.mark.asyncio
async def test_update_with_no_value_does_not_call_encrypt(
    service: LLMApiKeyService, repo: MagicMock, secrets: MagicMock
) -> None:
    repo.update = AsyncMock(return_value=_key_row())

    await service.update("key-1", name="renamed", updated_by="user-1")

    secrets.encrypt.assert_not_called()
    repo.update.assert_awaited_once_with("key-1", {"name": "renamed"})


@pytest.mark.asyncio
async def test_update_with_value_encrypts_and_omits_raw_value_from_audit(
    service: LLMApiKeyService, repo: MagicMock, secrets: MagicMock, audit_log: AsyncMock
) -> None:
    repo.update = AsyncMock(return_value=_key_row())
    secrets.encrypt = MagicMock(return_value="ENC:new")

    await service.update("key-1", value="new-secret", updated_by="user-1")

    secrets.encrypt.assert_called_once_with("new-secret")
    update_fields = repo.update.call_args.args[1]
    assert update_fields == {"value_encrypted": "ENC:new"}
    audit_details = audit_log.record.call_args.kwargs["details"]
    assert "new-secret" not in str(audit_details)
    assert audit_details["fields_changed"] == ["value"]


@pytest.mark.asyncio
async def test_update_returns_none_when_key_missing(
    service: LLMApiKeyService, repo: MagicMock
) -> None:
    repo.update = AsyncMock(return_value=None)

    result = await service.update("missing", name="x", updated_by="user-1")

    assert result is None


@pytest.mark.asyncio
async def test_delete_unlinks_models_using_key_before_deleting(
    service: LLMApiKeyService, repo: MagicMock, model_repo: MagicMock
) -> None:
    repo.delete = AsyncMock()
    model_repo.count_models_using_key = AsyncMock(return_value=2)
    model_repo.unlink_key_and_disable = AsyncMock()

    result = await service.delete("key-1", deleted_by="user-1")

    model_repo.unlink_key_and_disable.assert_awaited_once_with("key-1")
    repo.delete.assert_awaited_once_with("key-1")
    assert result.model_count == 2


@pytest.mark.asyncio
async def test_delete_skips_unlink_when_no_models_use_key(
    service: LLMApiKeyService, repo: MagicMock, model_repo: MagicMock
) -> None:
    repo.delete = AsyncMock()
    model_repo.count_models_using_key = AsyncMock(return_value=0)
    model_repo.unlink_key_and_disable = AsyncMock()

    await service.delete("key-1", deleted_by="user-1")

    model_repo.unlink_key_and_disable.assert_not_called()
    repo.delete.assert_awaited_once_with("key-1")
