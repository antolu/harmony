from __future__ import annotations

import scrapy


class PageItem(scrapy.Item):
    url = scrapy.Field()
    html = scrapy.Field()
    depth = scrapy.Field()
