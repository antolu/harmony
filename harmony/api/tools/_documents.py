from __future__ import annotations

import ipaddress
import json
import socket
import typing
from pathlib import Path
from urllib.parse import urlparse

import bs4
import httpx
import pydantic

from harmony.api.services import DocumentCache
from harmony.core import CorruptDocumentError
from harmony.core import default_registry as parser_registry

REQUEST_TIMEOUT = 30.0
MAX_DOCUMENT_SIZE = 50 * 1024 * 1024

_BLOCKED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("169.254.0.0/16"),
]

_SSRF_ERROR = "Error: URL blocked — private/internal addresses are not permitted."


def _is_private_address(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
        addrs = socket.getaddrinfo(host, None)
        for addr in addrs:
            ip = ipaddress.ip_address(addr[4][0])
            if any(ip in net for net in _BLOCKED_NETWORKS):
                return True
    except Exception:
        return True
    return False


async def _fetch_and_parse(
    url: str,
    cache: DocumentCache,
    validate: typing.Callable[[httpx.Response], str | None],
    parse: typing.Callable[[httpx.Response], str],
) -> str:
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.get(url, follow_redirects=False)
        response.raise_for_status()
        content_length = len(response.content)
        if content_length > MAX_DOCUMENT_SIZE:
            return json.dumps({
                "error": f"Document too large: {content_length} bytes (max {MAX_DOCUMENT_SIZE})"
            })
        validation_error = validate(response)
        if validation_error:
            return json.dumps({"error": validation_error})
        result = parse(response)
        cache.set(url, result)
        return result


async def _fetch_with_cache(  # noqa: PLR0911
    url: str,
    cache: DocumentCache,
    validate: typing.Callable[[httpx.Response], str | None],
    parse: typing.Callable[[httpx.Response], str],
) -> str:
    """Unified fetch helper for URL and PDF tools with caching and validation."""
    cached = cache.get(url)
    if cached:
        return cached

    if not url.startswith(("http://", "https://")):
        return json.dumps({"error": "URL must start with http:// or https://"})

    if _is_private_address(url):
        return _SSRF_ERROR

    try:
        return await _fetch_and_parse(url, cache, validate, parse)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"HTTP {e.response.status_code}: {url}"})
    except httpx.TimeoutException:
        return json.dumps({"error": f"Timeout fetching URL: {url}"})
    except CorruptDocumentError as e:
        return json.dumps({"error": f"Failed to parse document: {e!s}"})
    except Exception as e:
        return json.dumps({"error": f"Failed to fetch URL: {e!s}"})


class FetchURLTool:
    """Tool to fetch and extract text from web pages."""

    name = "fetch_url"
    description = (
        "Fetch a web page and extract its text content. "
        "Use this when the user asks about a specific URL or website. "
        "Returns the page title and main content."
    )
    parameters: typing.ClassVar[dict[str, pydantic.JsonValue]] = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The HTTP(S) URL to fetch",
            }
        },
        "required": ["url"],
    }

    def __init__(self, document_cache: DocumentCache) -> None:
        self._cache = document_cache

    async def execute(self, url: str) -> str:
        def validate(response: httpx.Response) -> str | None:
            return None

        def parse(response: httpx.Response) -> str:
            soup = bs4.BeautifulSoup(response.text, "lxml")
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text(separator=" ", strip=True)
            text = " ".join(text.split())
            return json.dumps(
                {
                    "url": url,
                    "title": title,
                    "content": text,
                    "type": "html",
                    "size": len(text),
                },
                indent=2,
            )

        return await _fetch_with_cache(url, self._cache, validate, parse)


class FetchPDFTool:
    """Tool to download and parse PDF documents."""

    name = "fetch_pdf"
    description = (
        "Download a PDF document from a URL and extract its text content. "
        "Use this when the user asks about a PDF file. "
        "Returns the document title, text content, and page count."
    )
    parameters: typing.ClassVar[dict[str, pydantic.JsonValue]] = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The HTTP(S) URL to the PDF file",
            }
        },
        "required": ["url"],
    }

    def __init__(self, document_cache: DocumentCache) -> None:
        self._cache = document_cache

    async def execute(self, url: str) -> str:
        def validate(response: httpx.Response) -> str | None:
            content_type = response.headers.get("content-type", "")
            if "pdf" not in content_type.lower() and not url.endswith(".pdf"):
                return f"URL does not appear to be a PDF (Content-Type: {content_type})"
            return None

        def parse(response: httpx.Response) -> str:
            temp_path = Path(f"/tmp/{url.rsplit('/', maxsplit=1)[-1]}")
            temp_path.write_bytes(response.content)
            try:
                parser = parser_registry.get_parser("application/pdf", ".pdf")
                if not parser:
                    return json.dumps({"error": "PDF parser not available"})
                title, content = parser.parse(temp_path)
                return json.dumps(
                    {
                        "url": url,
                        "title": title or temp_path.stem,
                        "content": content,
                        "type": "pdf",
                        "size": len(content),
                    },
                    indent=2,
                )
            finally:
                if temp_path.exists():
                    temp_path.unlink()

        return await _fetch_with_cache(url, self._cache, validate, parse)


class FetchDocumentTool:
    """Universal document fetcher with auto-detection."""

    name = "fetch_document"
    description = (
        "Fetch and parse any supported document type (PDF, DOCX, XLSX, ODT, Markdown, TXT, CSV). "
        "Auto-detects the document type from URL extension and Content-Type header. "
        "Use this when the user asks about a document of unknown type."
    )
    parameters: typing.ClassVar[dict[str, pydantic.JsonValue]] = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The HTTP(S) URL to the document",
            }
        },
        "required": ["url"],
    }

    def __init__(self, document_cache: DocumentCache) -> None:
        self._cache = document_cache

    @staticmethod
    def _detect_document_type(content_type: str, extension: str) -> str:
        content_lower = content_type.lower()
        ext_lower = extension.lower()

        TYPE_MAP: list[tuple[str, list[str], list[str]]] = [
            ("pdf", ["pdf"], [".pdf"]),
            ("docx", ["word"], [".docx", ".doc"]),
            ("xlsx", ["excel", "spreadsheet"], [".xlsx", ".xls"]),
            ("odt", ["opendocument"], [".odt", ".ods", ".odp"]),
            ("markdown", ["markdown"], [".md", ".markdown", ".mdown", ".mkd"]),
            ("txt", ["text/plain"], [".txt"]),
            ("csv", ["text/csv"], [".csv"]),
        ]

        return next(
            (
                doc_type
                for doc_type, ct_keywords, exts in TYPE_MAP
                if any(kw in content_lower for kw in ct_keywords) or ext_lower in exts
            ),
            "unknown",
        )

    async def execute(self, url: str) -> str:  # noqa: PLR0911
        cached = self._cache.get(url)
        if cached:
            return cached

        if not url.startswith(("http://", "https://")):
            return json.dumps({"error": "URL must start with http:// or https://"})

        if _is_private_address(url):
            return _SSRF_ERROR

        try:
            return await self._fetch_document(url)
        except httpx.HTTPStatusError as e:
            return json.dumps({"error": f"HTTP {e.response.status_code}: {url}"})
        except httpx.TimeoutException:
            return json.dumps({"error": f"Timeout fetching document: {url}"})
        except CorruptDocumentError as e:
            return json.dumps({"error": f"Failed to parse document: {e!s}"})
        except Exception as e:
            return json.dumps({"error": f"Failed to fetch document: {e!s}"})

    async def _fetch_document(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(url, follow_redirects=False)
            response.raise_for_status()

        content_length = len(response.content)
        if content_length > MAX_DOCUMENT_SIZE:
            return json.dumps({
                "error": f"Document too large: {content_length} bytes (max {MAX_DOCUMENT_SIZE})"
            })

        content_type = response.headers.get("content-type", "")
        extension = Path(url).suffix

        parser = parser_registry.get_parser(content_type, extension)
        if not parser:
            return json.dumps({
                "error": f"Unsupported document type: {content_type} ({extension}). "
                f"Supported: PDF, DOCX, XLSX, ODT, TXT, CSV"
            })

        filename = url.rsplit("/", maxsplit=1)[-1] or "document"
        temp_path = Path(f"/tmp/{filename}")
        temp_path.write_bytes(response.content)

        try:
            title, content = parser.parse(temp_path)
            doc_type = self._detect_document_type(content_type, extension)
            result = json.dumps(
                {
                    "url": url,
                    "title": title or temp_path.stem,
                    "content": content,
                    "type": doc_type,
                    "size": len(content),
                },
                indent=2,
            )
            self._cache.set(url, result)
            return result
        finally:
            if temp_path.exists():
                temp_path.unlink()
