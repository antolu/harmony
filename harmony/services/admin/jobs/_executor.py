from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from harmony.models import Job


@typing.runtime_checkable
class JobExecutor(typing.Protocol):
    """Backend that runs a job's command and streams its logs.

    Implementations: SubprocessJobExecutor (dev) and KubernetesJobExecutor (prod),
    selected by Settings.job_executor. The Protocol covers only the cross-backend
    operations; backend-specific controls (subprocess pause/resume) live on the
    concrete class.
    """

    async def submit(self, job: Job, command: list[str], env: dict[str, str]) -> str:
        """Launch the job command and return an execution handle/id."""
        ...

    async def wait(self, job_id: str) -> int | None:
        """Wait for the job to complete and return its exit code, or None if unknown."""
        ...

    async def cancel(self, job: Job, *, force: bool = False) -> None:
        """Cancel a running job. No-op if the job is not (or no longer) running."""
        ...

    def pause(self, job: Job) -> None:
        """Pause a running job. Backends that cannot pause raise NotImplementedError."""
        ...

    def resume(self, job: Job) -> None:
        """Resume a paused job. Backends that cannot pause raise NotImplementedError."""
        ...

    def get_log_stream(self, job: Job) -> AsyncIterator[str]:
        """Stream the job's log lines."""
        ...
