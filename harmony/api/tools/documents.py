from __future__ import annotations

import json
import typing
from pathlib import Path

import bs4
import httpx

from harmony.api.services.document_cache import document_cache
from harmony.indexer.parsers import (
    CorruptDocumentError,
)
from harmony.indexer.parsers import (
    default_registry as parser_registry,
)

# Timeout for HTTP requests (30 seconds)
REQUEST_TIMEOUT = 30.0

# Maximum document size (50MB)
MAX_DOCUMENT_SIZE = 50 * 1024 * 1024


class FetchURLTool:
    """Tool to fetch and extract text from web pages."""

    name = "fetch_url"
    description = (
        "Fetch a web page and extract its text content. "
        "Use this when the user asks about a specific URL or website. "
        "Returns the page title and main content."
    )
    parameters: typing.ClassVar[dict[str, typing.Any]] = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The HTTP(S) URL to fetch",
            }
        },
        "required": ["url"],
    }

    async def execute(self, url: str) -> str:  # noqa: PLR0911 - multiple error handling returns
        """Fetch URL and extract text content."""
        try:
            # Check cache first
            cached = document_cache.get(url)
            if cached:
                return cached

            # Validate URL
            if not url.startswith(("http://", "https://")):
                return json.dumps({"error": "URL must start with http:// or https://"})

            # Fetch page
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()

                # Check size
                content_length = len(response.content)
                if content_length > MAX_DOCUMENT_SIZE:
                    return json.dumps({
                        "error": f"Document too large: {content_length} bytes (max {MAX_DOCUMENT_SIZE})"
                    })

                # Parse HTML
                soup = bs4.BeautifulSoup(response.text, "lxml")

                # Extract title
                title_tag = soup.find("title")
                title = title_tag.get_text(strip=True) if title_tag else ""

                # Remove scripts and styles
                for script in soup(["script", "style"]):
                    script.decompose()

                # Extract text
                text = soup.get_text(separator=" ", strip=True)
                text = " ".join(text.split())  # Normalize whitespace

                result = json.dumps(
                    {
                        "url": url,
                        "title": title,
                        "content": text,
                        "type": "html",
                        "size": len(text),
                    },
                    indent=2,
                )

                # Cache the result
                document_cache.set(url, result)

                return result

        except httpx.HTTPStatusError as e:
            return json.dumps({"error": f"HTTP {e.response.status_code}: {url}"})
        except httpx.TimeoutException:
            return json.dumps({"error": f"Timeout fetching URL: {url}"})
        except Exception as e:
            return json.dumps({"error": f"Failed to fetch URL: {e!s}"})


class FetchPDFTool:
    """Tool to download and parse PDF documents."""

    name = "fetch_pdf"
    description = (
        "Download a PDF document from a URL and extract its text content. "
        "Use this when the user asks about a PDF file. "
        "Returns the document title, text content, and page count."
    )
    parameters: typing.ClassVar[dict[str, typing.Any]] = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The HTTP(S) URL to the PDF file",
            }
        },
        "required": ["url"],
    }

    async def execute(self, url: str) -> str:  # noqa: PLR0911 - multiple error handling returns
        """Download and parse PDF."""
        try:
            # Check cache first
            cached = document_cache.get(url)
            if cached:
                return cached

            # Validate URL
            if not url.startswith(("http://", "https://")):
                return json.dumps({"error": "URL must start with http:// or https://"})

            # Download PDF
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()

                # Check size
                content_length = len(response.content)
                if content_length > MAX_DOCUMENT_SIZE:
                    return json.dumps({
                        "error": f"PDF too large: {content_length} bytes (max {MAX_DOCUMENT_SIZE})"
                    })

                # Check content type
                content_type = response.headers.get("content-type", "")
                if "pdf" not in content_type.lower() and not url.endswith(".pdf"):
                    return json.dumps({
                        "error": f"URL does not appear to be a PDF (Content-Type: {content_type})"
                    })

                # Create temporary path for parser
                temp_path = Path(f"/tmp/{url.rsplit('/', maxsplit=1)[-1]}")
                temp_path.write_bytes(response.content)

                try:
                    # Parse with PDFParser
                    parser = parser_registry.get_parser("application/pdf", ".pdf")
                    if not parser:
                        return json.dumps({"error": "PDF parser not available"})

                    title, content = parser.parse(temp_path)

                    result = json.dumps(
                        {
                            "url": url,
                            "title": title or temp_path.stem,
                            "content": content,
                            "type": "pdf",
                            "size": len(content),
                        },
                        indent=2,
                    )

                    # Cache the result
                    document_cache.set(url, result)

                    return result

                finally:
                    # Clean up temp file
                    if temp_path.exists():
                        temp_path.unlink()

        except httpx.HTTPStatusError as e:
            return json.dumps({"error": f"HTTP {e.response.status_code}: {url}"})
        except httpx.TimeoutException:
            return json.dumps({"error": f"Timeout fetching PDF: {url}"})
        except CorruptDocumentError as e:
            return json.dumps({"error": f"Failed to parse PDF: {e!s}"})
        except Exception as e:
            return json.dumps({"error": f"Failed to fetch PDF: {e!s}"})


class FetchDocumentTool:
    """Universal document fetcher with auto-detection."""

    name = "fetch_document"
    description = (
        "Fetch and parse any supported document type (PDF, DOCX, XLSX, ODT, Markdown, TXT, CSV). "
        "Auto-detects the document type from URL extension and Content-Type header. "
        "Use this when the user asks about a document of unknown type."
    )
    parameters: typing.ClassVar[dict[str, typing.Any]] = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The HTTP(S) URL to the document",
            }
        },
        "required": ["url"],
    }

    @staticmethod
    def _detect_document_type(content_type: str, extension: str) -> str:  # noqa: PLR0911 - checking multiple document types
        """Detect document type from content type and extension."""
        content_lower = content_type.lower()
        ext_lower = extension.lower()

        if "pdf" in ext_lower or "pdf" in content_lower:
            return "pdf"
        if "word" in content_lower or extension == ".docx":
            return "docx"
        if "excel" in content_lower or extension == ".xlsx":
            return "xlsx"
        if "opendocument" in content_lower or extension == ".odt":
            return "odt"
        if (
            extension in {".md", ".markdown", ".mdown", ".mkd"}
            or "markdown" in content_lower
        ):
            return "markdown"
        if extension == ".txt":
            return "txt"
        if extension == ".csv":
            return "csv"
        return "unknown"

    async def execute(self, url: str) -> str:  # noqa: PLR0911 - multiple error handling returns
        """Download and parse document with auto-detection."""
        try:
            # Check cache first
            cached = document_cache.get(url)
            if cached:
                return cached

            # Validate URL
            if not url.startswith(("http://", "https://")):
                return json.dumps({"error": "URL must start with http:// or https://"})

            # Download document
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()

                # Check size
                content_length = len(response.content)
                if content_length > MAX_DOCUMENT_SIZE:
                    return json.dumps({
                        "error": f"Document too large: {content_length} bytes (max {MAX_DOCUMENT_SIZE})"
                    })

                # Detect type
                content_type = response.headers.get("content-type", "")
                extension = Path(url).suffix

                # Get appropriate parser
                parser = parser_registry.get_parser(content_type, extension)
                if not parser:
                    return json.dumps({
                        "error": f"Unsupported document type: {content_type} ({extension}). "
                        f"Supported: PDF, DOCX, XLSX, ODT, TXT, CSV"
                    })

                # Save to temporary file
                filename = url.rsplit("/", maxsplit=1)[-1] or "document"
                temp_path = Path(f"/tmp/{filename}")
                temp_path.write_bytes(response.content)

                try:
                    # Parse document
                    title, content = parser.parse(temp_path)

                    # Determine document type from parser
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

                    # Cache the result
                    document_cache.set(url, result)

                    return result

                finally:
                    # Clean up temp file
                    if temp_path.exists():
                        temp_path.unlink()

        except httpx.HTTPStatusError as e:
            return json.dumps({"error": f"HTTP {e.response.status_code}: {url}"})
        except httpx.TimeoutException:
            return json.dumps({"error": f"Timeout fetching document: {url}"})
        except CorruptDocumentError as e:
            return json.dumps({"error": f"Failed to parse document: {e!s}"})
        except Exception as e:
            return json.dumps({"error": f"Failed to fetch document: {e!s}"})


# Tool instances
fetch_url_tool = FetchURLTool()
fetch_pdf_tool = FetchPDFTool()
fetch_document_tool = FetchDocumentTool()
