from __future__ import annotations

import pytest


@pytest.mark.skip(reason="not implemented — AUDIT-01")
@pytest.mark.integration
def test_audit_event_recorded() -> None:
    pass


@pytest.mark.skip(reason="not implemented — AUDIT-02")
@pytest.mark.integration
def test_query_audit_log() -> None:
    pass


@pytest.mark.skip(reason="not implemented — AUDIT-03")
@pytest.mark.integration
def test_audit_retention_cleanup() -> None:
    pass


@pytest.mark.skip(reason="not implemented — AUDIT-04")
@pytest.mark.integration
def test_search_query_logged() -> None:
    pass
