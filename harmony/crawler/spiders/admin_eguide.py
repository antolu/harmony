from __future__ import annotations

import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

from harmony.crawler.items import PageItem


class AdminEguideSpider(CrawlSpider):
    name = "admin_eguide"

    start_urls: list[str] = []
    allowed_domains: list[str] = []

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

    def parse_page(self, response: scrapy.http.Response) -> PageItem:
        yield PageItem(
            url=response.url,
            html=response.text,
            depth=response.meta.get("depth", 0),
        )
