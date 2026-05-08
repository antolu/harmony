from __future__ import annotations

import inspect


def test_infrastructure_endpoint_exists() -> None:
    import importlib

    mod = importlib.import_module("harmony.api.routes.admin._infrastructure")
    assert hasattr(mod, "router")
    routes = [r.path for r in mod.router.routes]
    assert any("infrastructure" in r or "config" in r for r in routes)


def test_pipeline_settings_includes_agentic_fields() -> None:
    from harmony.api.routes import settings as settings_route

    source = inspect.getsource(settings_route)
    assert "agentic_max_refinement_rounds" in source or "agentic" in source
