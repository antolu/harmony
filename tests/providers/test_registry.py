from __future__ import annotations

from unittest.mock import MagicMock


def test_builtin_providers_registered() -> None:
    from harmony.providers._registry import ProviderRegistry

    registry = ProviderRegistry()
    types = [t["type"] for t in registry.list_types()]
    assert "web-crawler" in types
    assert "filesystem" in types


def test_list_types_includes_schema() -> None:
    from harmony.providers._registry import ProviderRegistry

    registry = ProviderRegistry()
    for entry in registry.list_types():
        assert "type" in entry
        assert "display_name" in entry
        assert "description" in entry
        assert "schema" in entry


def test_unknown_entrypoint_skipped() -> None:
    from harmony.providers._registry import _register_entry_point

    class NotAProvider:
        pass

    bad_ep = MagicMock()
    bad_ep.name = "bad-provider"
    bad_ep.value = "some.module:NotAProvider"
    bad_ep.load.return_value = NotAProvider

    providers: dict[str, type] = {}
    _register_entry_point(bad_ep, providers)

    assert "bad-provider" not in providers
