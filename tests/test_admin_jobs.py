from __future__ import annotations

import pytest


@pytest.mark.skip(reason="not implemented — JOB-01")
@pytest.mark.integration
def test_list_jobs_with_progress() -> None:
    pass


@pytest.mark.skip(reason="not implemented — JOB-02")
@pytest.mark.integration
def test_stream_job_logs_sse() -> None:
    pass


@pytest.mark.skip(reason="not implemented — JOB-03")
@pytest.mark.integration
def test_get_historical_logs() -> None:
    pass


@pytest.mark.skip(reason="not implemented — JOB-04")
@pytest.mark.integration
def test_cancel_job() -> None:
    pass


@pytest.mark.skip(reason="not implemented — JOB-05")
@pytest.mark.integration
def test_retrigger_job() -> None:
    pass
