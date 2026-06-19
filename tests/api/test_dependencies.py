from __future__ import annotations

from unittest.mock import MagicMock


def _make_request(**state_attrs: object) -> MagicMock:
    request = MagicMock()
    for key, val in state_attrs.items():
        setattr(request.app.state, key, val)
    return request


def test_get_search_service() -> None:
    from harmony.api.dependencies import get_search_service

    svc = MagicMock()
    req = _make_request(search_service=svc)
    assert get_search_service(req) is svc


def test_get_es_service() -> None:
    from harmony.api.dependencies import get_es_service

    svc = MagicMock()
    req = _make_request(es_service=svc)
    assert get_es_service(req) is svc


def test_get_llm_service() -> None:
    from harmony.api.dependencies import get_llm_service

    svc = MagicMock()
    req = _make_request(llm_service=svc)
    assert get_llm_service(req) is svc


def test_get_conversation_service() -> None:
    from harmony.api.dependencies import get_conversation_service

    svc = MagicMock()
    req = _make_request(conversation_service=svc)
    assert get_conversation_service(req) is svc


def test_get_tool_registry() -> None:
    from harmony.api.dependencies import get_tool_registry

    svc = MagicMock()
    req = _make_request(tool_registry=svc)
    assert get_tool_registry(req) is svc


def test_get_prompt_manager() -> None:
    from harmony.api.dependencies import get_prompt_manager

    svc = MagicMock()
    req = _make_request(prompt_manager=svc)
    assert get_prompt_manager(req) is svc


def test_get_orchestrator() -> None:
    from harmony.api.dependencies import get_orchestrator

    svc = MagicMock()
    req = _make_request(orchestrator=svc)
    assert get_orchestrator(req) is svc


def test_get_pipeline_config() -> None:
    from harmony.api.dependencies import get_pipeline_config
    from harmony.api.services import PipelineConfig

    cfg = PipelineConfig()
    req = _make_request(pipeline_config=cfg)
    assert get_pipeline_config(req) is cfg


def test_get_safety_lists_repo() -> None:
    from harmony.api.dependencies import get_safety_lists_repo
    from harmony.db.repositories import SafetyListsRepo

    pool = MagicMock()
    req = _make_request(db_pool=pool)
    repo = get_safety_lists_repo(req)
    assert isinstance(repo, SafetyListsRepo)
    assert repo._pool is pool


def test_get_auth_sessions_repo() -> None:
    from harmony.api.dependencies import get_auth_sessions_repo
    from harmony.db.repositories import AuthSessionsRepo

    pool = MagicMock()
    req = _make_request(db_pool=pool)
    repo = get_auth_sessions_repo(req)
    assert isinstance(repo, AuthSessionsRepo)
    assert repo._pool is pool


def test_get_users_repo() -> None:
    from harmony.api.dependencies import get_users_repo
    from harmony.db.repositories import UsersRepo

    pool = MagicMock()
    req = _make_request(db_pool=pool)
    repo = get_users_repo(req)
    assert isinstance(repo, UsersRepo)
    assert repo._pool is pool


def test_get_token_usage_repo() -> None:
    from harmony.api.dependencies import get_token_usage_repo
    from harmony.db.repositories import TokenUsageRepo

    pool = MagicMock()
    req = _make_request(db_pool=pool)
    repo = get_token_usage_repo(req)
    assert isinstance(repo, TokenUsageRepo)
    assert repo._pool is pool


def test_get_message_feedback_repo() -> None:
    from harmony.api.dependencies import get_message_feedback_repo
    from harmony.db.repositories import MessageFeedbackRepo

    pool = MagicMock()
    req = _make_request(db_pool=pool)
    repo = get_message_feedback_repo(req)
    assert isinstance(repo, MessageFeedbackRepo)
    assert repo._pool is pool
