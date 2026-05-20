from __future__ import annotations

import inspect

from harmony.api.routes import chat
from harmony.db import redis_client


def test_process_tool_calls_return_type() -> None:
    """_process_tool_calls must be typed as AsyncGenerator, not AsyncIterator."""
    source = inspect.getsource(chat._process_tool_calls)
    assert "AsyncGenerator" in source, (
        "_process_tool_calls is a generator — annotate return type as AsyncGenerator[str, None]"
    )


def test_redis_client_has_future_annotations() -> None:
    source = inspect.getsource(redis_client)
    assert "from __future__ import annotations" in source
