from __future__ import annotations

import pytest


@pytest.mark.skip(reason="not implemented — LLM-01")
@pytest.mark.integration
def test_model_registry_crud() -> None:
    pass


@pytest.mark.skip(reason="not implemented — LLM-02")
@pytest.mark.integration
def test_test_llm_connectivity() -> None:
    pass


@pytest.mark.skip(reason="not implemented — SETTINGS-03")
@pytest.mark.integration
def test_api_key_encryption() -> None:
    pass


@pytest.mark.skip(
    reason="LLM-04 deferred to Phase 6 — requires K8s vLLM infrastructure"
)
@pytest.mark.integration
def test_configure_vllm_serving() -> None:
    pass
