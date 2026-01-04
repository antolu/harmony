from __future__ import annotations

import collections.abc
import typing

import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

from harmony.crawler.items import PageItem


class AdminEguideSpider(CrawlSpider):
    name = "admin_eguide"

    start_urls: typing.ClassVar[list[str]] = []
    allowed_domains: typing.ClassVar[list[str]] = []

    rules = (
        Rule(
            LinkExtractor(
                deny=(
                    r"auth\.cern\.ch",
                    r"/logout",
                    r"/sign-out",
                    r"/logoff",
                    r"javascript:",
                    r"/node/\d+",
                ),
                deny_extensions=[],
            ),
            callback="parse_page",
            follow=True,
        ),
    )

    def parse_page(  # noqa: PLR6301
        self, response: scrapy.http.Response
    ) -> collections.abc.Generator[PageItem, None, None]:
        yield PageItem(
            url=response.url,
            html=response.text,
            depth=response.meta.get("depth", 0),
        )
