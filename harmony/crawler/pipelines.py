from __future__ import annotations

import fcntl
import json
import re
import typing
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import bs4
from langdetect import LangDetectException, detect

from harmony.crawler.items import DocumentItem, PageItem

# Constants
MIN_TEXT_LENGTH_FOR_DETECTION = 50


class HTMLExpanderPipeline:
    @staticmethod
    def process_item(item: PageItem, spider: typing.Any) -> PageItem:
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
            elem["class"] = [c for c in classes if c not in {"hidden", "collapsed"}]

        item["html"] = str(soup)
        return item


class FileStoragePipeline:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        # No longer need a single metadata file
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_crawler(cls, crawler: typing.Any) -> FileStoragePipeline:
        return cls(output_dir=crawler.settings.get("OUTPUT_DIR", "output"))

    @staticmethod
    def detect_language(html: str) -> str:
        """Detect language from HTML content."""
        soup = bs4.BeautifulSoup(html, "lxml")

        for script in soup(["script", "style"]):
            script.decompose()

        text = soup.get_text(separator=" ", strip=True)
        text = " ".join(text.split())

        if len(text) < MIN_TEXT_LENGTH_FOR_DETECTION:
            return "unknown"

        try:
            return detect(text)
        except LangDetectException:
            return "unknown"

    def process_item(self, item: PageItem, spider: typing.Any) -> PageItem:
        parsed = urlparse(item["url"])

        path_parts = parsed.path.lstrip("/").rstrip("/")

        if not path_parts:
            filepath = self.output_dir / parsed.netloc / "index.html"
        else:
            base_path = self.output_dir / parsed.netloc / path_parts

            # Only treat as file if it has a valid file extension (not version numbers)
            has_file_extension = (
                base_path.suffix
                and len(base_path.suffix) > 1
                and base_path.suffix.lstrip(".").isalpha()  # .html, .pdf not .5
            )
            filepath = base_path if has_file_extension else base_path / "index.html"

        if filepath.exists() and filepath.is_dir():
            filepath /= "index.html"

        # Check all ancestors for file/directory conflicts
        for ancestor in reversed(list(filepath.parents)):
            if ancestor == self.output_dir:
                break
            if ancestor.exists() and ancestor.is_file():
                ancestor_file = ancestor
                str(ancestor_file.relative_to(self.output_dir))
                ancestor_file.rename(ancestor_file.with_suffix(".html.bak"))
                ancestor.mkdir(parents=True, exist_ok=True)
                new_index = ancestor / "index.html"
                ancestor_file.with_suffix(".html.bak").rename(new_index)

                # TODO: Update metadata.jsonl to reflect path change
                # (not critical since indexer resolves paths relatively)
                break

        filepath.parent.mkdir(parents=True, exist_ok=True)

        filepath.write_text(item["html"], encoding="utf-8")

        language = self.detect_language(item["html"])

        metadata = {
            "url": item["url"],
            "file_path": str(filepath.relative_to(self.output_dir)),
            "depth": item["depth"],
            "crawled_at": datetime.now(UTC).isoformat(),
            "domain": parsed.netloc,
            "path": parsed.path,
            "language": language,
        }

        # Write to domain-specific metadata.jsonl with file locking
        domain_dir = self.output_dir / parsed.netloc
        domain_dir.mkdir(parents=True, exist_ok=True)
        metadata_file = domain_dir / "metadata.jsonl"

        # Atomic append with exclusive file lock
        with metadata_file.open("a", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(json.dumps(metadata, ensure_ascii=False) + "\n")
                f.flush()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        return item


class DocumentStoragePipeline:
    """Pipeline for storing binary documents (PDF, DOCX, etc.) for future parsing."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.documents_dir = self.output_dir / "documents"
        self.documents_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_crawler(cls, crawler: typing.Any) -> DocumentStoragePipeline:
        return cls(output_dir=crawler.settings.get("OUTPUT_DIR", "output"))

    def process_item(
        self, item: DocumentItem | PageItem, spider: typing.Any
    ) -> DocumentItem | PageItem:
        # Only process DocumentItems
        if not isinstance(item, DocumentItem):
            return item

        parsed = urlparse(item["url"])

        # Create directory structure based on domain and path
        path_parts = parsed.path.lstrip("/").rstrip("/")

        if not path_parts:
            # Shouldn't happen for documents, but handle it
            filepath = self.documents_dir / parsed.netloc / "document"
        else:
            filepath = self.documents_dir / parsed.netloc / path_parts

        # Ensure parent directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Write binary content
        filepath.write_bytes(item["content"])

        # Write metadata to domain-specific metadata.jsonl
        metadata = {
            "url": item["url"],
            "file_path": str(filepath.relative_to(self.output_dir)),
            "depth": item["depth"],
            "crawled_at": datetime.now(UTC).isoformat(),
            "domain": parsed.netloc,
            "path": parsed.path,
            "content_type": item["content_type"],
            "type": "document",  # Mark as document for indexer
        }

        # Write to domain-specific metadata.jsonl with file locking
        domain_dir = self.documents_dir / parsed.netloc
        domain_dir.mkdir(parents=True, exist_ok=True)
        metadata_file = domain_dir / "metadata.jsonl"

        # Atomic append with exclusive file lock
        with metadata_file.open("a", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(json.dumps(metadata, ensure_ascii=False) + "\n")
                f.flush()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        return item
