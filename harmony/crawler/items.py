from __future__ import annotations

import scrapy


class PageItem(scrapy.Item):
    url = scrapy.Field()
    html = scrapy.Field()
    depth = scrapy.Field()


class DocumentItem(scrapy.Item):
    url = scrapy.Field()
    content = scrapy.Field()
    content_type = scrapy.Field()
    depth = scrapy.Field()
