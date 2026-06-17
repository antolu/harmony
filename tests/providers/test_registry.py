from __future__ import annotations

import pytest


@pytest.mark.skip(reason="not implemented yet")
def test_builtin_providers_registered() -> None:
    from harmony.providers._registry import ProviderRegistry  # noqa: PLC2701

    registry = ProviderRegistry()
    types = [t["type"] for t in registry.list_types()]
    assert "web-crawler" in types
    assert "filesystem" in types


@pytest.mark.skip(reason="not implemented yet")
def test_list_types_includes_schema() -> None:
    from harmony.providers._registry import ProviderRegistry  # noqa: PLC2701

    registry = ProviderRegistry()
    for entry in registry.list_types():
        assert "type" in entry
        assert "display_name" in entry
        assert "description" in entry
        assert "schema" in entry


@pytest.mark.skip(reason="not implemented yet")
def test_unknown_entrypoint_skipped() -> None:
    from harmony.providers._registry import ProviderRegistry  # noqa: PLC2701

    registry = ProviderRegistry()
    registry.discover()
