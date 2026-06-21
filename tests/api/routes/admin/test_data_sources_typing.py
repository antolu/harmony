from __future__ import annotations

import inspect
import pathlib

from harmony.api.routes.admin import data_sources
from harmony.api.services.admin._data_sources import (  # noqa: PLC2701
    DataSourcesService,
)
from harmony.db.repositories import DataSourcesRepo


def test_repo_methods_use_data_source_id() -> None:
    for name in ("get", "update", "delete", "update_last_run"):
        params = inspect.signature(getattr(DataSourcesRepo, name)).parameters
        assert "data_source_id" in params
        assert "id" not in params


def test_service_methods_use_data_source_id() -> None:
    for name in ("get", "update", "delete"):
        params = inspect.signature(getattr(DataSourcesService, name)).parameters
        assert "data_source_id" in params
        assert "id" not in params


def test_route_handlers_use_data_source_id() -> None:
    for name in ("get_data_source", "update_data_source", "delete_data_source"):
        params = inspect.signature(getattr(data_sources, name)).parameters
        assert "data_source_id" in params
        assert "id" not in params


def test_route_path_templates_use_data_source_id() -> None:
    for route in data_sources.router.routes:
        path = getattr(route, "path", "")
        assert "{id}" not in path


def test_no_remaining_a002_noqa() -> None:
    for path_str in (
        "harmony/db/repositories/__init__.py",
        "harmony/api/services/admin/_data_sources.py",
        "harmony/api/routes/admin/data_sources.py",
    ):
        content = pathlib.Path(path_str).read_text(encoding="utf-8")
        assert "noqa: A002" not in content
