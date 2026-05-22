from __future__ import annotations

import pytest


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_compose_logging_uses_json_driver() -> None:
    """OBS-02: Docker Compose logging is configured to use a JSON-compatible driver or stdout JSON without cloud dependency."""
