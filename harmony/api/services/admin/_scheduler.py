from __future__ import annotations

import logging
import typing

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class ScheduleService:
    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler | None = None

    async def initialize(self, db_url: str) -> None:
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
        jobstore = SQLAlchemyJobStore(url=db_url, tablename="apscheduler_jobs")
        self._scheduler = AsyncIOScheduler(
            jobstores={"default": jobstore}, timezone="UTC"
        )
        self._scheduler.start()
        logger.info("ScheduleService initialized with SQLAlchemy job store")

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
        except Exception:
            return False
        else:
            return True

    async def list_schedules(self) -> list[dict[str, typing.Any]]:
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
        ]

    async def add_nightly_job(
        self, job_id: str, func: typing.Callable[..., typing.Any], hour: int = 2
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


def _trigger_crawl_and_index(config_name: str) -> None:
    logger.info(f"Scheduled crawl triggered for config: {config_name}")
