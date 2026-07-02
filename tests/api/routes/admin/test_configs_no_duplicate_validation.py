from __future__ import annotations

import inspect


def test_configs_does_not_inline_es_validation() -> None:
    from harmony.api.routes.admin import _configs as configs

    source = inspect.getsource(configs)
    assert "httpx" not in source, (
        "configs.py must not inline ES validation with httpx — delegate to service_config"
    )
