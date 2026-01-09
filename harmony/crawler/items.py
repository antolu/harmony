from __future__ import annotations

import scrapy


class PageItem(scrapy.Item):
    url = scrapy.Field()
    html = scrapy.Field()
    depth = scrapy.Field()
    last_modified = scrapy.Field()
    etag = scrapy.Field()
    status_code = scrapy.Field()
    content_type = scrapy.Field()
    _content_hash = scrapy.Field()
    _filepath = scrapy.Field()


class DocumentItem(scrapy.Item):
    url = scrapy.Field()
    content = scrapy.Field()
    content_type = scrapy.Field()
    depth = scrapy.Field()
    last_modified = scrapy.Field()
    etag = scrapy.Field()
    status_code = scrapy.Field()
    _content_hash = scrapy.Field()
    _filepath = scrapy.Field()
