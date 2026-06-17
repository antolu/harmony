from __future__ import annotations

import dataclasses

import pytest


def test_web_crawler_run_returns_two_specs() -> None:
    from harmony.providers._web_crawler import WebCrawlerProvider  # noqa: PLC2701

    provider = WebCrawlerProvider(config={}, config_name="my-config")
    specs = provider.run()

    assert len(specs) == 2
    assert specs[0].entrypoint == "harmony-crawl"
    assert specs[0].args == ["--config", "my-config"]
    assert specs[1].entrypoint == "harmony-index"
    assert specs[1].args == ["--source", "elasticsearch"]


def test_filesystem_run_returns_one_spec() -> None:
    from harmony.providers._filesystem import FilesystemProvider  # noqa: PLC2701

    provider = FilesystemProvider(
        config={"root_path": "/data", "source_name": "my-source"},
        data_source_id="ds-123",
    )
    specs = provider.run()

    assert len(specs) == 1
    assert specs[0].entrypoint == "harmony-ingest-fs"
    assert specs[0].args == ["--data-source-id", "ds-123"]


def test_provider_job_spec_is_frozen() -> None:
    from harmony.providers._base import ProviderJobSpec  # noqa: PLC2701

    spec = ProviderJobSpec(entrypoint="harmony-crawl", args=[], env={})
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.entrypoint = "other"  # type: ignore[misc]
