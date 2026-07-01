# ruff: noqa
from __future__ import annotations

from harmony._mod_replace import replace_modname
from harmony.tools._documents import FetchDocumentTool, FetchPDFTool, FetchURLTool
from harmony.tools._mcp import MCPServerLoader, MCPTool
from harmony.tools._registry import Tool, ToolRegistry
from harmony.tools._search import GetDocumentDetailsTool, SearchDocumentsTool

replace_modname(FetchDocumentTool, __name__)
replace_modname(FetchPDFTool, __name__)
replace_modname(FetchURLTool, __name__)
replace_modname(GetDocumentDetailsTool, __name__)
replace_modname(MCPServerLoader, __name__)
replace_modname(MCPTool, __name__)
replace_modname(SearchDocumentsTool, __name__)
replace_modname(Tool, __name__)
replace_modname(ToolRegistry, __name__)

__all__ = [
    "FetchDocumentTool",
    "FetchPDFTool",
    "FetchURLTool",
    "GetDocumentDetailsTool",
    "MCPServerLoader",
    "MCPTool",
    "SearchDocumentsTool",
    "Tool",
    "ToolRegistry",
]
