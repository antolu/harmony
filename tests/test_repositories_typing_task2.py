from __future__ import annotations

import inspect
import pathlib
import typing

from harmony.api.services.admin._models import ModelRegistryRow  # noqa: PLC2701
from harmony.db import repositories


def test_webhook_repo_returns_typed_dict_and_no_valid_type_ignore() -> None:
    hints = typing.get_type_hints(repositories.WebhookData)
    assert hints["id"] is str
    assert hints["url"] is str

    list_hints = typing.get_type_hints(repositories.WebhookRepo.list)
    assert list_hints["return"] == list[repositories.WebhookData]

    get_hints = typing.get_type_hints(repositories.WebhookRepo.get)
    assert get_hints["return"] == repositories.WebhookData | None

    create_source = inspect.getsource(repositories.WebhookRepo.create)
    assert "type: ignore[valid-type]" not in create_source

    get_for_event_source = inspect.getsource(repositories.WebhookRepo.get_for_event)
    assert "type: ignore[valid-type]" not in get_for_event_source
    get_for_event_hints = typing.get_type_hints(repositories.WebhookRepo.get_for_event)
    assert get_for_event_hints["return"] == list[repositories.WebhookData]


def test_model_registry_repo_returns_model_registry_row() -> None:
    hints = typing.get_type_hints(repositories.ModelRegistryRepo.list_all)
    assert hints["return"] == list[ModelRegistryRow]

    get_hints = typing.get_type_hints(repositories.ModelRegistryRepo.get)
    assert get_hints["return"] == ModelRegistryRow | None


def test_indexer_config_repo_returns_typed_dict() -> None:
    hints = typing.get_type_hints(repositories.IndexerConfigData)
    assert hints["id"] is str

    get_hints = typing.get_type_hints(repositories.IndexerConfigRepo.get)
    assert get_hints["return"] == repositories.IndexerConfigData | None


def test_no_remaining_valid_type_ignore_in_repositories() -> None:
    content = pathlib.Path("harmony/db/repositories/__init__.py").read_text(
        encoding="utf-8"
    )
    assert "type: ignore[valid-type]" not in content


def test_authz_context_no_union_attr_ignore() -> None:
    content = pathlib.Path("harmony/api/authz/_context.py").read_text(encoding="utf-8")
    assert "type: ignore[union-attr]" not in content


def test_token_tracking_no_union_attr_ignore() -> None:
    content = pathlib.Path("harmony/api/observability/_token_tracking.py").read_text(
        encoding="utf-8"
    )
    assert "type: ignore[union-attr]" not in content
