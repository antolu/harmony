from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from harmony.api.services.admin import SCHEDULER_LEADER_LOCK_KEY, ScheduleService


@pytest.fixture
def scheduler() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(scheduler: MagicMock) -> ScheduleService:
    svc = ScheduleService()
    svc._scheduler = scheduler
    return svc


def _with_lock_result(service: ScheduleService, *, granted: bool) -> AsyncMock:
    conn = AsyncMock()
    cursor = AsyncMock()
    cursor.fetchone = AsyncMock(return_value=(granted,))
    conn.execute = AsyncMock(return_value=cursor)
    service._leader_conn = conn
    return conn


async def test_try_acquire_leadership_sets_leader_when_lock_granted(
    service: ScheduleService,
) -> None:
    conn = _with_lock_result(service, granted=True)

    acquired = await service._try_acquire_leadership()

    assert acquired is True
    assert service._is_leader is True
    conn.execute.assert_awaited_once()
    assert SCHEDULER_LEADER_LOCK_KEY in conn.execute.await_args.args[1]


async def test_try_acquire_leadership_stays_nonleader_when_lock_denied(
    service: ScheduleService,
) -> None:
    _with_lock_result(service, granted=False)

    acquired = await service._try_acquire_leadership()

    assert acquired is False
    assert service._is_leader is False


def test_leader_resumes_scheduler(
    service: ScheduleService, scheduler: MagicMock
) -> None:
    service._is_leader = True

    service._apply_leadership()

    scheduler.resume.assert_called_once()
    scheduler.pause.assert_not_called()


def test_nonleader_pauses_scheduler(
    service: ScheduleService, scheduler: MagicMock
) -> None:
    service._is_leader = False

    service._apply_leadership()

    scheduler.pause.assert_called_once()
    scheduler.resume.assert_not_called()


async def test_recheck_resumes_after_acquiring_leadership(
    service: ScheduleService, scheduler: MagicMock
) -> None:
    async def _acquire() -> bool:
        service._is_leader = True
        return True

    service._try_acquire_leadership = _acquire  # type: ignore[method-assign]

    await service._recheck_leadership()

    scheduler.resume.assert_called_once()


async def test_recheck_noop_when_already_leader(
    service: ScheduleService, scheduler: MagicMock
) -> None:
    service._is_leader = True
    service._try_acquire_leadership = AsyncMock()  # type: ignore[method-assign]

    await service._recheck_leadership()

    service._try_acquire_leadership.assert_not_awaited()
    scheduler.resume.assert_not_called()
