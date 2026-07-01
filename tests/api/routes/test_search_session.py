from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from harmony.api.routes import _search_session as session  # noqa: PLC2701
from harmony.models import AnonymousIdentity, UserIdentity

pytestmark = pytest.mark.asyncio


def _user(role: str = "operator") -> UserIdentity:
    user = MagicMock(spec=UserIdentity)
    user.id = "u1"
    user.harmony_role = role
    return user


async def test_resolve_model_errors_when_none() -> None:
    resolved, err = await session.resolve_and_authorize_model(
        None, AnonymousIdentity(), None, None
    )
    assert resolved is None
    assert err is not None
    assert "No model selected" in err


async def test_resolve_model_resolves_via_registry() -> None:
    registry = MagicMock()
    registry.resolve_litellm_model_id = AsyncMock(return_value="provider/model-x")
    resolved, err = await session.resolve_and_authorize_model(
        "model-x", AnonymousIdentity(), None, registry
    )
    assert resolved == "provider/model-x"
    assert err is None


async def test_resolve_model_blocks_disallowed_role() -> None:
    policy = MagicMock()
    policy.get_allowed_roles = AsyncMock(return_value=["admin"])
    resolved, err = await session.resolve_and_authorize_model(
        "model-x", _user("operator"), policy, None
    )
    assert resolved is None
    assert err is not None
    assert "not permitted" in err


async def test_resolve_model_allows_permitted_role() -> None:
    policy = MagicMock()
    policy.get_allowed_roles = AsyncMock(return_value=["operator"])
    resolved, err = await session.resolve_and_authorize_model(
        "model-x", _user("operator"), policy, None
    )
    assert resolved == "model-x"
    assert err is None


def test_user_id_of() -> None:
    assert session.user_id_of(_user()) == "u1"
    assert session.user_id_of(AnonymousIdentity()) is None


async def test_maybe_generate_title_skips_existing_conversation() -> None:
    conv = MagicMock()
    conv.generate_title_async = AsyncMock()
    event = await session.maybe_generate_title_event(
        is_new_conversation=False,
        conversation_id="c1",
        user_id="u1",
        query="q",
        answer="a",
        conversation_service=conv,
        llm_service=MagicMock(),
    )
    assert event is None
    conv.generate_title_async.assert_not_called()


async def test_maybe_generate_title_skips_empty_answer() -> None:
    conv = MagicMock()
    conv.generate_title_async = AsyncMock()
    event = await session.maybe_generate_title_event(
        is_new_conversation=True,
        conversation_id="c1",
        user_id="u1",
        query="q",
        answer="",
        conversation_service=conv,
        llm_service=MagicMock(),
    )
    assert event is None
    conv.generate_title_async.assert_not_called()


async def test_maybe_generate_title_emits_event() -> None:
    conv = MagicMock()
    conv.generate_title_async = AsyncMock(return_value="A Nice Title")
    event = await session.maybe_generate_title_event(
        is_new_conversation=True,
        conversation_id="c1",
        user_id="u1",
        query="q",
        answer="a",
        conversation_service=conv,
        llm_service=MagicMock(),
    )
    assert event is not None
    assert event.startswith("event: title\n")
    payload = json.loads(event.split("data: ", 1)[1])
    assert payload == {"conversation_id": "c1", "title": "A Nice Title"}
