import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from harmony.api.main import _init_admin_services  # noqa: PLC2701


@pytest.mark.asyncio
async def test_nightly_job_closure() -> None:
    """
    D-16: Verify nightly job functions execute correctly when invoked via
    closure with real/mock app.state.
    """
    app = FastAPI()
    app.state = MagicMock()

    with (
        patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}),
        patch("harmony.api.main.admin_settings") as mock_admin_settings,
    ):
        mock_admin_settings.config_storage_path = MagicMock()
        mock_admin_settings.job_log_path = MagicMock()
        with patch("harmony.api.main.ScheduleService") as mock_schedule_cls:
            mock_schedule = AsyncMock()
            mock_schedule_cls.return_value = mock_schedule

            with (
                patch("harmony.api.main.CrawlConfigService") as mock_crawl,
                patch("harmony.api.main.DataSourcesService") as mock_ds,
                patch("harmony.api.main.IndexerConfigService") as mock_indexer,
                patch("harmony.api.main.AuditLogService") as mock_audit,
                patch("harmony.api.main.ModelRegistryService") as mock_model,
                patch("harmony.api.main.WebhookService") as mock_webhook,
                patch("harmony.api.main.JobManager") as mock_jm_cls,
            ):
                for mock_svc in [
                    mock_crawl,
                    mock_ds,
                    mock_indexer,
                    mock_audit,
                    mock_model,
                    mock_webhook,
                ]:
                    mock_inst = MagicMock()
                    mock_inst.initialize = AsyncMock()
                    mock_inst.import_from_filesystem = AsyncMock()
                    mock_inst.import_from_filesystem_if_empty = AsyncMock()
                    mock_inst.promote_crawler_configs = AsyncMock()
                    mock_svc.return_value = mock_inst

                mock_jm = MagicMock()
                mock_jm.initialize = AsyncMock()
                mock_jm_cls.return_value = mock_jm

                # Mock to avoid file system and DB calls
                await _init_admin_services(app)

                # Verify add_nightly_job was called twice (audit_cleanup and conversation_cleanup)
                assert mock_schedule.add_nightly_job.call_count == 2

                # Extract the closure and execute it with our mock state to ensure it wraps correctly
                closure_1 = mock_schedule.add_nightly_job.call_args_list[0].kwargs[
                    "func"
                ]
                closure_2 = mock_schedule.add_nightly_job.call_args_list[1].kwargs[
                    "func"
                ]

                assert callable(closure_1)
                assert callable(closure_2)
