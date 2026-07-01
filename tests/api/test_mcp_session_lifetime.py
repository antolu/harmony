from __future__ import annotations

import inspect
import pathlib

from harmony.tools import _mcp as mcp


def test_session_stored_before_context_exits() -> None:
    """MCPServerLoader must use AsyncExitStack to keep sessions alive."""
    src = pathlib.Path("harmony/tools/_mcp.py").read_text(encoding="utf-8")
    assert "AsyncExitStack" in src, (
        "MCPServerLoader must use AsyncExitStack to keep sessions alive"
    )


def test_load_server_does_not_use_async_with_session() -> None:
    """_load_server must not use async with ClientSession — that tears it down."""
    source = inspect.getsource(mcp.MCPServerLoader._load_server)
    assert "async with" not in source or "ClientSession" not in source, (
        "_load_server must not use 'async with ClientSession' — session is torn down on exit"
    )
