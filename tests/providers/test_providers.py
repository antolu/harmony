from __future__ import annotations

import pytest


@pytest.mark.skip(reason="not implemented yet")
def test_web_crawler_run_returns_two_specs() -> None: ...


@pytest.mark.skip(reason="not implemented yet")
def test_filesystem_run_returns_one_spec() -> None: ...


@pytest.mark.skip(reason="not implemented yet")
def test_provider_job_spec_is_frozen() -> None:
    from harmony.providers._base import ProviderJobSpec  # noqa: PLC2701

    spec = ProviderJobSpec(entrypoint="harmony-crawl", args=[], env={})
    with pytest.raises(AttributeError):
        spec.entrypoint = "other"  # type: ignore[misc]
