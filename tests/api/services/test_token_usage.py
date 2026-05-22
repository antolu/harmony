from __future__ import annotations

import pytest


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_usage_query_groups_by_model_user_date() -> None:
    """TOKEN-01: Usage records group by model, user, date, trace, endpoint, and agent step."""


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_litellm_callback_emits_usage_event_async() -> None:
    """TOKEN-02: LiteLLM callback queues usage event asynchronously without blocking response."""


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_tracking_failure_does_not_block_response() -> None:
    """TOKEN-02: A failure in usage tracking does not propagate to or block the API response."""
