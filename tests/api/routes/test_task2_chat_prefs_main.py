from __future__ import annotations

import dataclasses

from harmony.api.main import app
from harmony.api.routes._preferences import PREFERENCE_DEFAULTS
from harmony.api.routes._simple_chat import AISearchRequest


def test_ai_search_request_has_model_field() -> None:
    r = AISearchRequest(query="test")
    assert r.model is None


def test_preferences_has_preference_defaults() -> None:
    assert dataclasses.is_dataclass(PREFERENCE_DEFAULTS)
    assert PREFERENCE_DEFAULTS.theme == "system"


def test_main_includes_conversations_router() -> None:
    url = app.url_path_for("list_conversations")
    assert str(url).startswith("/api/conversations"), (
        "/api/conversations not registered in main.py"
    )


def test_main_includes_feedback_router() -> None:
    url = app.url_path_for("submit_feedback")
    assert str(url).startswith("/api/feedback"), (
        "/api/feedback not registered in main.py"
    )


def test_main_includes_preferences_router() -> None:
    url = app.url_path_for("get_preferences")
    assert str(url).startswith("/api/preferences"), (
        "/api/preferences not registered in main.py"
    )
