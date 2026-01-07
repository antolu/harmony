from __future__ import annotations

import io
import json
import typing
from pathlib import Path

import bs4
import httpx

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

    async def execute(self, url: str) -> str:  # noqa: PLR6301
        """Fetch URL and extract text content."""
        try:
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

    async def execute(self, url: str) -> str:  # noqa: PLR6301, PLR0911
        """Download and parse PDF."""
        try:
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

                # Save to BytesIO
                io.BytesIO(response.content)

                # Create temporary path for parser
                temp_path = Path(f"/tmp/{url.rsplit('/', maxsplit=1)[-1]}")
                temp_path.write_bytes(response.content)

                try:
                    # Parse with PDFParser
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
        "Fetch and parse any supported document type (PDF, DOCX, XLSX, ODT, TXT, CSV). "
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

    async def execute(self, url: str) -> str:  # noqa: PLR6301, PLR0911, PLR0912
        """Download and parse document with auto-detection."""
        try:
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
                    doc_type = "unknown"
                    if "pdf" in extension.lower() or "pdf" in content_type.lower():
                        doc_type = "pdf"
                    elif "word" in content_type.lower() or extension == ".docx":
                        doc_type = "docx"
                    elif "excel" in content_type.lower() or extension == ".xlsx":
                        doc_type = "xlsx"
                    elif "opendocument" in content_type.lower() or extension == ".odt":
                        doc_type = "odt"
                    elif extension == ".txt":
                        doc_type = "txt"
                    elif extension == ".csv":
                        doc_type = "csv"

                    return json.dumps(
                        {
                            "url": url,
                            "title": title or temp_path.stem,
                            "content": content,
                            "type": doc_type,
                            "size": len(content),
                        },
                        indent=2,
                    )

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
