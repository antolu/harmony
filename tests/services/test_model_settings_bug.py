from __future__ import annotations

import asyncio
import typing

import pytest

import harmony.api.services.admin._model_settings as ms  # noqa: PLC2701


def _make_pool_getter(pool: object) -> typing.Any:
    async def _get() -> object:
        await asyncio.sleep(0)
        return pool

    return _get


@pytest.mark.asyncio
async def test_db_get_passes_pool_not_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_db_get must pass a pool to ServiceConfigRepo, not a connection."""
    calls: list[str] = []

    class FakeRepo:
        def __init__(self, pool: object) -> None:
            calls.append(type(pool).__name__)

        async def get(self, key: str) -> dict | None:
            return None

    class FakePool:
        pass

    monkeypatch.setattr(
        "harmony.api.services.admin._model_settings.get_async_pool",
        _make_pool_getter(FakePool()),
    )
    monkeypatch.setattr(
        "harmony.api.services.admin._model_settings.ServiceConfigRepo", FakeRepo
    )

    await ms._db_get("some_key")
    assert calls == ["FakePool"]


@pytest.mark.asyncio
async def test_db_save_passes_pool_not_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_db_save must pass a pool to ServiceConfigRepo, not a connection."""
    calls: list[str] = []

    class FakeRepo:
        def __init__(self, pool: object) -> None:
            calls.append(type(pool).__name__)

        async def upsert(
            self,
            key: str,
            value: str,
            description: object = None,
            *,
            validated: bool = True,
        ) -> None:
            pass

    class FakePool:
        pass

    monkeypatch.setattr(
        "harmony.api.services.admin._model_settings.get_async_pool",
        _make_pool_getter(FakePool()),
    )
    monkeypatch.setattr(
        "harmony.api.services.admin._model_settings.ServiceConfigRepo", FakeRepo
    )

    await ms._db_save("some_key", "some_value")
    assert calls == ["FakePool"]
