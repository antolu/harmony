from __future__ import annotations

import pytest


def test_feedback_router_importable() -> None:
    from harmony.api.routes.feedback import router  # type: ignore[import]

    assert router is not None


def test_feedback_router_has_post_route() -> None:
    from harmony.api.routes.feedback import router  # type: ignore[import]

    paths = [r.path for r in router.routes]
    assert "/" in paths


def test_feedback_router_has_delete_route() -> None:
    from harmony.api.routes.feedback import router  # type: ignore[import]

    paths = [r.path for r in router.routes]
    assert "/{conversation_id}/{message_id}" in paths


def test_feedback_router_has_get_conversation_route() -> None:
    from harmony.api.routes.feedback import router  # type: ignore[import]

    paths = [r.path for r in router.routes]
    assert "/conversation/{conversation_id}" in paths


def test_feedback_request_validates_rating_up_or_down() -> None:
    from harmony.api.routes.feedback import FeedbackRequest  # type: ignore[import]

    req = FeedbackRequest(conversation_id="conv-1", message_id=1, rating="up")
    assert req.rating == "up"

    req2 = FeedbackRequest(conversation_id="conv-1", message_id=1, rating="down")
    assert req2.rating == "down"


def test_feedback_request_rejects_invalid_rating() -> None:
    import pydantic
    from harmony.api.routes.feedback import FeedbackRequest  # type: ignore[import]

    with pytest.raises(pydantic.ValidationError):
        FeedbackRequest(conversation_id="conv-1", message_id=1, rating="invalid")


def test_preferences_router_importable() -> None:
    from harmony.api.routes.preferences import router  # type: ignore[import]

    assert router is not None


def test_preferences_router_has_get_route() -> None:
    from harmony.api.routes.preferences import router  # type: ignore[import]

    paths = [r.path for r in router.routes]
    assert "/" in paths


def test_preferences_router_has_patch_route() -> None:
    from harmony.api.routes.preferences import router  # type: ignore[import]

    paths = [r.path for r in router.routes]
    assert "/" in paths


def test_preferences_update_accepts_valid_theme() -> None:
    from harmony.api.routes.preferences import PreferencesUpdate  # type: ignore[import]

    u = PreferencesUpdate(theme="light")
    assert u.theme == "light"

    u2 = PreferencesUpdate(theme="dark")
    assert u2.theme == "dark"

    u3 = PreferencesUpdate(theme="system")
    assert u3.theme == "system"


def test_preferences_update_rejects_invalid_theme() -> None:
    import pydantic
    from harmony.api.routes.preferences import PreferencesUpdate  # type: ignore[import]

    with pytest.raises(pydantic.ValidationError):
        PreferencesUpdate(theme="invalid")


def test_preferences_update_allows_none_theme() -> None:
    from harmony.api.routes.preferences import PreferencesUpdate  # type: ignore[import]

    u = PreferencesUpdate(theme=None)
    assert u.theme is None
