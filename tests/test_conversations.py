from __future__ import annotations

import inspect
from pathlib import Path

from harmony.services._conversation import ConversationService  # noqa: PLC2701


def test_get_messages_accepts_user_id_param() -> None:
    sig = inspect.signature(ConversationService.get_messages)
    assert "user_id" in sig.parameters, (
        "ConversationService.get_messages must accept user_id parameter (Plan 05 adds this)"
    )


def test_user_id_column_in_migration() -> None:
    migration_path = Path("alembic/versions/0006_add_conversation_user_id.py")
    assert migration_path.exists(), (
        "Migration 0006_add_conversation_user_id.py must exist (Plan 05 creates this)"
    )
