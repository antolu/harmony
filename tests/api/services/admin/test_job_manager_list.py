from __future__ import annotations

import inspect


def test_list_jobs_does_not_return_in_memory_dict() -> None:
    from harmony.api.services.admin import job_manager as jm

    source = inspect.getsource(jm.JobManager.list_jobs)
    assert "self._jobs" not in source, (
        "list_jobs() must query Postgres, not return the in-memory _jobs dict"
    )
    assert "SELECT" in source or "await" in source, (
        "list_jobs() must be async and query the DB"
    )
