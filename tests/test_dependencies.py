from unittest.mock import Mock

from fastapi import Request

from harmony.api._dependencies import (
    get_auth_sessions_repo,
    get_message_feedback_repo,
    get_safety_lists_repo,
    get_token_usage_repo,
    get_users_repo,
)
from harmony.db.repositories import (
    AuthSessionsRepo,
    MessageFeedbackRepo,
    SafetyListsRepo,
    TokenUsageRepo,
    UsersRepo,
)


def test_repo_dependencies() -> None:
    """
    D-14: Verify each Depends() factory returns the correct repo type
    bound to app.state.db_pool.
    """
    mock_app = Mock()
    mock_app.state.db_pool = Mock()

    request = Mock(spec=Request)
    request.app = mock_app

    auth_repo = get_auth_sessions_repo(request)
    assert isinstance(auth_repo, AuthSessionsRepo)
    assert auth_repo._pool == mock_app.state.db_pool

    users_repo = get_users_repo(request)
    assert isinstance(users_repo, UsersRepo)
    assert users_repo._pool == mock_app.state.db_pool

    safety_repo = get_safety_lists_repo(request)
    assert isinstance(safety_repo, SafetyListsRepo)
    assert safety_repo._pool == mock_app.state.db_pool

    token_repo = get_token_usage_repo(request)
    assert isinstance(token_repo, TokenUsageRepo)
    assert token_repo._pool == mock_app.state.db_pool

    feedback_repo = get_message_feedback_repo(request)
    assert isinstance(feedback_repo, MessageFeedbackRepo)
    assert feedback_repo._pool == mock_app.state.db_pool
