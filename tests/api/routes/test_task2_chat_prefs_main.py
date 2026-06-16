from __future__ import annotations


def test_ai_search_request_has_model_field() -> None:
    from harmony.api.routes.chat import AISearchRequest

    r = AISearchRequest(query="test")
    assert hasattr(r, "model")
    assert r.model is None


def test_preferences_has_preference_defaults() -> None:
    import harmony.api.routes.preferences as prefs_mod

    defaults = getattr(prefs_mod, "PREFERENCE_DEFAULTS", None)
    assert defaults is not None, "PREFERENCE_DEFAULTS must be defined in preferences.py"
    assert isinstance(defaults, dict)
    assert "theme" in defaults
    assert defaults["theme"] == "system"


def test_main_includes_conversations_router() -> None:
    from harmony.api.main import app

    paths = [getattr(r, "path", "") for r in app.routes]
    assert any("/api/conversations" in p for p in paths), (
        "/api/conversations not registered in main.py"
    )


def test_main_includes_feedback_router() -> None:
    from harmony.api.main import app

    paths = [getattr(r, "path", "") for r in app.routes]
    assert any("/api/feedback" in p for p in paths), (
        "/api/feedback not registered in main.py"
    )


def test_main_includes_preferences_router() -> None:
    from harmony.api.main import app

    paths = [getattr(r, "path", "") for r in app.routes]
    assert any("/api/preferences" in p for p in paths), (
        "/api/preferences not registered in main.py"
    )
