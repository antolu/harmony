from __future__ import annotations

import inspect


def test_reset_does_not_access_raw_es_client() -> None:
    from harmony.api.routes.admin import reset

    source = inspect.getsource(reset)
    assert "es_service.client" not in source, (
        "reset.py must use ElasticsearchService methods, not es_service.client directly"
    )
    assert ".client.indices" not in source, (
        "reset.py must not call es_service.client.indices"
    )
