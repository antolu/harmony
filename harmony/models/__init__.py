from __future__ import annotations

from harmony._mod_replace import replace_modname
from harmony.models.job import Job, JobProgress, JobStatus, JobType
from harmony.models.user import AnonymousIdentity, UserIdentity

replace_modname(AnonymousIdentity, __name__)
replace_modname(Job, __name__)
replace_modname(JobProgress, __name__)
replace_modname(JobStatus, __name__)
replace_modname(UserIdentity, __name__)

__all__ = [
    "AnonymousIdentity",
    "Job",
    "JobProgress",
    "JobStatus",
    "JobType",
    "UserIdentity",
]
