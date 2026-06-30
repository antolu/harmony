from __future__ import annotations

import logging
import typing

import psycopg
import psycopg_pool
import pydantic
from apscheduler.jobstores.base import (  # type: ignore[import-untyped]  # apscheduler lacks stubs
    JobLookupError as APSJobLookupError,
)
from apscheduler.jobstores.sqlalchemy import (  # type: ignore[import-untyped]  # apscheduler lacks stubs
    SQLAlchemyJobStore,
)
from apscheduler.schedulers.asyncio import (  # type: ignore[import-untyped]  # apscheduler lacks stubs
    AsyncIOScheduler,
)
from apscheduler.triggers.cron import (  # type: ignore[import-untyped]  # apscheduler lacks stubs
    CronTrigger,
)
from apscheduler.triggers.interval import (  # type: ignore[import-untyped]  # apscheduler lacks stubs
    IntervalTrigger,
)

logger = logging.getLogger(__name__)

SCHEDULER_LEADER_LOCK_KEY = 0x48524D5343484544  # "HRMSCHED" namespaced advisory key
_LEADER_RECHECK_SECONDS = 30


class ScheduleService:
    """Crawl and nightly job scheduler with single-leader execution.

    Each replica binds a scheduler to the shared ``apscheduler_jobs`` table, so
    schedule CRUD works on any pod. Only the replica holding the Postgres
    advisory lock keeps its scheduler resumed and fires triggers; non-leaders
    stay paused. A periodic recheck promotes a non-leader once the previous
    leader releases the lock.
    """

    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler | None = None
        self._pool: psycopg_pool.AsyncConnectionPool | None = None
        self._leader_conn: psycopg.AsyncConnection[typing.Any] | None = None
        self._is_leader: bool = False

    async def initialize(
        self, db_url: str, pool: psycopg_pool.AsyncConnectionPool
    ) -> None:
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
        jobstore = SQLAlchemyJobStore(url=db_url, tablename="apscheduler_jobs")
        self._scheduler = AsyncIOScheduler(
            jobstores={"default": jobstore}, timezone="UTC"
        )
        self._scheduler.start(paused=True)

        self._pool = pool
        await self._acquire_leader_conn()
        await self._try_acquire_leadership()
        self._apply_leadership()
        self._scheduler.add_job(
            func=self._recheck_leadership,
            trigger=IntervalTrigger(seconds=_LEADER_RECHECK_SECONDS),
            id="scheduler-leader-recheck",
            name="scheduler-leader-recheck",
            replace_existing=True,
        )
        logger.info(
            "ScheduleService initialized with SQLAlchemy job store "
            f"(leader={self._is_leader})"
        )

    @property
    def is_leader(self) -> bool:
        return self._is_leader

    async def _acquire_leader_conn(self) -> None:
        if self._pool is None:
            msg = "ScheduleService not initialized"
            raise RuntimeError(msg)
        self._leader_conn = await self._pool.getconn()

    async def _try_acquire_leadership(self) -> bool:
        if self._leader_conn is None or self._is_leader:
            return self._is_leader
        cursor = await self._leader_conn.execute(
            "SELECT pg_try_advisory_lock(%s)", (SCHEDULER_LEADER_LOCK_KEY,)
        )
        row = await cursor.fetchone()
        self._is_leader = bool(row and row[0])
        return self._is_leader

    def _apply_leadership(self) -> None:
        if self._scheduler is None:
            return
        if self._is_leader:
            self._scheduler.resume()
        else:
            self._scheduler.pause()

    async def _recheck_leadership(self) -> None:
        if self._is_leader:
            return
        if await self._try_acquire_leadership():
            self._apply_leadership()
            logger.info("ScheduleService acquired scheduler leadership after handover")

    async def add_crawl_schedule(self, config_name: str, cron_expr: str) -> None:
        if self._scheduler is None:
            msg = "ScheduleService not initialized"
            raise RuntimeError(msg)
        trigger = CronTrigger.from_crontab(cron_expr)
        self._scheduler.add_job(
            func=_trigger_crawl_and_index,
            trigger=trigger,
            id=f"crawl-{config_name}",
            name=f"Crawl {config_name}",
            replace_existing=True,
            kwargs={"config_name": config_name},
        )

    async def remove_crawl_schedule(self, config_name: str) -> bool:
        if self._scheduler is None:
            return False
        try:
            self._scheduler.remove_job(f"crawl-{config_name}")
        except APSJobLookupError:
            return False
        else:
            return True

    async def list_schedules(self) -> list[dict[str, pydantic.JsonValue]]:
        if self._scheduler is None:
            return []
        return [
            {
                "id": job.id,
                "name": job.name,
                "config_name": job.id.removeprefix("crawl-"),
                "next_run_time": str(job.next_run_time),
                "cron": str(job.trigger),
            }
            for job in self._scheduler.get_jobs()
            if job.id.startswith("crawl-")
        ]

    async def add_nightly_job(
        self,
        job_id: str,
        func: typing.Callable[..., typing.Awaitable[None]],
        hour: int = 2,
    ) -> None:
        if self._scheduler is None:
            msg = "ScheduleService not initialized"
            raise RuntimeError(msg)
        trigger = CronTrigger(hour=hour, minute=0, timezone="UTC")
        self._scheduler.add_job(
            func=func,
            trigger=trigger,
            id=job_id,
            name=job_id,
            replace_existing=True,
        )

    async def shutdown(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        if self._leader_conn is not None and self._pool is not None:
            try:
                if self._is_leader:
                    await self._leader_conn.execute(
                        "SELECT pg_advisory_unlock(%s)", (SCHEDULER_LEADER_LOCK_KEY,)
                    )
            finally:
                await self._pool.putconn(self._leader_conn)
                self._leader_conn = None
                self._is_leader = False


def _trigger_crawl_and_index(config_name: str) -> None:
    logger.info(f"Scheduled crawl triggered for config: {config_name}")
