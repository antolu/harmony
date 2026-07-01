from __future__ import annotations

import inspect

from harmony.tools import _registry as registry  # noqa: PLC2701
from harmony.tools import _search as search  # noqa: PLC2701


def test_search_tools_list_removed() -> None:
    assert not hasattr(search, "SEARCH_TOOLS"), "SEARCH_TOOLS is dead code — remove it"


def test_execute_tool_removed() -> None:
    assert not hasattr(search, "execute_tool"), "execute_tool is dead code — remove it"


def test_search_no_empty_type_checking() -> None:
    source = inspect.getsource(search)
    assert "TYPE_CHECKING:\n    pass" not in source


def test_registry_no_empty_type_checking() -> None:
    source = inspect.getsource(registry)
    assert "TYPE_CHECKING:\n    pass" not in source
