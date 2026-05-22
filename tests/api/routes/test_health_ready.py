from __future__ import annotations

import pytest


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_health_returns_liveness_only() -> None:
    """OBS-03: GET /health returns a liveness status only, with no dependency checks."""


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_ready_returns_dependency_status_per_dep() -> None:
    """OBS-03: GET /ready returns per-dependency status for each configured dependency."""


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_ready_returns_503_when_es_down() -> None:
    """OBS-03: GET /ready returns 503 when Elasticsearch is unreachable."""
