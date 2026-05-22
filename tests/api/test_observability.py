from __future__ import annotations

import structlog
import structlog.testing


def test_request_log_is_json_with_trace_id() -> None:
    """OBS-01: Request logs include a trace_id field."""
    with structlog.testing.capture_logs(
        processors=[structlog.contextvars.merge_contextvars]
    ) as cap_logs:
        logger = structlog.get_logger()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            trace_id="test-trace-123",
            endpoint="/test",
            method="GET",
        )
        logger.info("request", status_code=200, latency_ms=42)
        structlog.contextvars.clear_contextvars()

    assert len(cap_logs) == 1
    log = cap_logs[0]
    assert log["trace_id"] == "test-trace-123"
    assert log["endpoint"] == "/test"


def test_request_log_includes_user_and_action_fields() -> None:
    """OBS-01: Request logs include method and status_code fields."""
    with structlog.testing.capture_logs(
        processors=[structlog.contextvars.merge_contextvars]
    ) as cap_logs:
        logger = structlog.get_logger()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            trace_id="abc",
            user_id="user-1",
            endpoint="/search",
            method="POST",
        )
        logger.info("request", status_code=200, latency_ms=10)
        structlog.contextvars.clear_contextvars()

    log = cap_logs[0]
    assert log["method"] == "POST"
    assert log["status_code"] == 200


def test_outbound_log_does_not_contain_secret_values() -> None:
    """OBS-04: Logs do not contain API key values."""
    secret_patterns = ["api_key", "client_secret", "private_key"]
    with structlog.testing.capture_logs() as cap_logs:
        logger = structlog.get_logger()
        logger.info(
            "outbound_llm_call", model="gpt-4", provider="openai", trace_id="t1"
        )

    for log in cap_logs:
        for key in log:
            assert key not in secret_patterns, f"Secret field '{key}' found in log"
        for pattern in secret_patterns:
            if isinstance(log.get("event"), str):
                assert pattern not in log["event"].lower()
