from __future__ import annotations

import pytest


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_request_log_is_json_with_trace_id() -> None:
    """OBS-01: Request logs are emitted as JSON and include a trace_id field."""


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_request_log_includes_user_and_action_fields() -> None:
    """OBS-01: Request logs include user identity and action fields without content snippets."""


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_outbound_llm_call_log_includes_provider_model_trace() -> None:
    """OBS-04: Outbound LLM call logs include provider, model, and trace fields."""


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_outbound_log_does_not_contain_secret_values() -> None:
    """OBS-04: Outbound LLM call logs do not contain API keys or other secret values."""
