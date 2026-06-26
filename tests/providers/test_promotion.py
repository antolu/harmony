from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from harmony.api.services.admin import (
    DataSourcesService,
)
from harmony.db.repositories import CrawlConfigData

_NOW = datetime.now(UTC)


def _crawl_config_data(name: str, config_json: dict[str, object]) -> CrawlConfigData:
    return CrawlConfigData(
        id="00000000-0000-0000-0000-000000000000",
        name=name,
        description=None,
        config_json=config_json,
        created_by=None,
        created_at=_NOW,
        updated_at=_NOW,
    )


@pytest.mark.asyncio
async def test_promote_creates_web_crawler_instances() -> None:
    service = DataSourcesService()
    service._repo = MagicMock()
    service._repo.create_if_not_exists = AsyncMock()

    crawl_config_service = MagicMock()
    crawl_config_service.list = AsyncMock(
        return_value=[
            _crawl_config_data("docs-site", {"start_urls": ["https://x.test"]}),
        ]
    )

    await service.promote_crawler_configs(crawl_config_service)

    service._repo.create_if_not_exists.assert_awaited_once_with(
        name="docs-site",
        provider_type="web-crawler",
        config_data={"start_urls": ["https://x.test"]},
    )


@pytest.mark.asyncio
async def test_promote_is_idempotent() -> None:
    """Repeated promotion always delegates to create_if_not_exists, which is the
    ON CONFLICT (name) DO NOTHING upsert that makes promotion safe to re-run.
    """
    service = DataSourcesService()
    service._repo = MagicMock()
    service._repo.create_if_not_exists = AsyncMock()

    crawl_config_service = MagicMock()
    crawl_config_service.list = AsyncMock(
        return_value=[_crawl_config_data("docs-site", {})]
    )

    await service.promote_crawler_configs(crawl_config_service)
    await service.promote_crawler_configs(crawl_config_service)

    assert service._repo.create_if_not_exists.await_count == 2
    first_call, second_call = service._repo.create_if_not_exists.await_args_list
    assert first_call == second_call
