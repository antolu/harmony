from __future__ import annotations

import inspect


def test_conversation_service_is_not_in_memory() -> None:
    from harmony.services import ConversationService

    source = inspect.getsource(ConversationService)
    assert "dict[" not in source or "_pool" in source, (
        "ConversationService must be backed by Postgres, not an in-memory dict"
    )
