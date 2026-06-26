from __future__ import annotations

import inspect

from harmony.api.routes import chat
from harmony.db import redis_client


def test_process_tool_calls_return_type() -> None:
    """_process_tool_calls emits into a StatusSink, it no longer yields SSE strings."""
    sig = inspect.signature(chat._process_tool_calls)
    assert sig.return_annotation in {"None", None}, (
        "_process_tool_calls is no longer a generator — it emits into a StatusSink "
        "parameter and should be annotated to return None"
    )


def test_redis_client_has_future_annotations() -> None:
    source = inspect.getsource(redis_client)
    assert "from __future__ import annotations" in source
