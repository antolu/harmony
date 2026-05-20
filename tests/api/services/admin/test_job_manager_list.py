from __future__ import annotations

import inspect


def test_list_jobs_does_not_return_in_memory_dict() -> None:
    from harmony.api.services.admin import JobManager

    source = inspect.getsource(JobManager.list_jobs)
    assert "JobsRepo" in source or "load_all" in source, (
        "list_jobs() must query Postgres via JobsRepo, not return the in-memory _jobs dict"
    )
    assert "await" in source, "list_jobs() must be async and query the DB"
