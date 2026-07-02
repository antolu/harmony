from __future__ import annotations

import pydantic

from ._base import BaseProvider, ProviderJobSpec
from .web_crawler import CrawlerConfig


class WebCrawlerProvider(BaseProvider):
    provider_type = "web-crawler"
    display_name = "Web Crawler"
    description = "Crawl websites and index pages via Scrapy"

    def __init__(self, config: dict[str, pydantic.JsonValue], config_name: str) -> None:
        self._config = config
        self._config_name = config_name

    @classmethod
    def config_schema(cls) -> dict[str, pydantic.JsonValue]:
        return CrawlerConfig.model_json_schema()

    def run(self) -> list[ProviderJobSpec]:
        return [
            ProviderJobSpec(
                entrypoint="harmony-crawl",
                args=["--config", self._config_name],
                env={},
            ),
            ProviderJobSpec(
                entrypoint="harmony-index",
                args=["--source", "elasticsearch"],
                env={},
            ),
        ]
