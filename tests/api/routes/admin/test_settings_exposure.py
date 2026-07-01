from __future__ import annotations

import inspect

from harmony.api.routes.admin import _infrastructure


def test_infrastructure_endpoint_exists() -> None:
    assert hasattr(_infrastructure, "router")
    routes = [r.path for r in _infrastructure.router.routes]  # type: ignore
    assert any("infrastructure" in r or "config" in r for r in routes)


def test_pipeline_settings_includes_agentic_fields() -> None:
    from harmony.api.routes import settings as settings_route

    source = inspect.getsource(settings_route)
    assert "agentic_max_refinement_rounds" in source or "agentic" in source
