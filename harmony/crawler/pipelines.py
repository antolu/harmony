from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import bs4

from harmony.crawler.items import PageItem


class HTMLExpanderPipeline:
    def process_item(self, item: PageItem, spider) -> PageItem:
        html = item["html"]
        soup = bs4.BeautifulSoup(html, "lxml")

        for details in soup.find_all("details"):
            details["open"] = ""

        for elem in soup.find_all(style=re.compile(r"display:\s*none")):
            style = elem.get("style", "")
            new_style = re.sub(r"display:\s*none;?", "", style)
            if new_style.strip():
                elem["style"] = new_style
            elif "style" in elem.attrs:
                del elem["style"]

        for elem in soup.find_all(class_=re.compile(r"(hidden|collapsed)")):
            classes = elem.get("class", [])
            elem["class"] = [c for c in classes if c not in ("hidden", "collapsed")]

        item["html"] = str(soup)
        return item


class FileStoragePipeline:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.metadata_file = self.output_dir / "metadata.jsonl"
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(output_dir=crawler.settings.get("OUTPUT_DIR", "output"))

    def process_item(self, item: PageItem, spider) -> PageItem:
        parsed = urlparse(item["url"])

        path_parts = parsed.path.lstrip("/").rstrip("/")

        if not path_parts:
            filepath = self.output_dir / parsed.netloc / "index.html"
        else:
            base_path = self.output_dir / parsed.netloc / path_parts

            if base_path.suffix:
                filepath = base_path
            else:
                filepath = base_path / "index.html"

        if filepath.exists() and filepath.is_dir():
            filepath = filepath / "index.html"

        if filepath.parent.exists() and filepath.parent.is_file():
            parent_file = filepath.parent
            parent_file.rename(parent_file.with_suffix(".html.bak"))
            filepath.parent.mkdir(parents=True, exist_ok=True)
            parent_file.with_suffix(".html.bak").rename(filepath.parent / "index.html")
        else:
            filepath.parent.mkdir(parents=True, exist_ok=True)

        filepath.write_text(item["html"], encoding="utf-8")

        metadata = {
            "url": item["url"],
            "file_path": str(filepath.relative_to(self.output_dir)),
            "depth": item["depth"],
            "crawled_at": datetime.now(timezone.utc).isoformat(),
            "domain": parsed.netloc,
            "path": parsed.path,
        }

        with self.metadata_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(metadata) + "\n")

        return item
