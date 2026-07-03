from __future__ import annotations

import pathlib


def test_conversation_service_is_not_in_memory() -> None:
    source = pathlib.Path("harmony/services/_conversation.py").read_text(
        encoding="utf-8"
    )
    assert "ConversationRepo" in source, (
        "ConversationService must be backed by the Postgres ConversationRepo, "
        "not an in-memory dict"
    )
