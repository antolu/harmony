from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from harmony.agents import (
    AgenticOrchestrator,
    AgentSuite,
    CriticAgent,
    QueryPlannerAgent,
    SearcherAgent,
    SynthesizerAgent,
)
from harmony.api.config import Settings
from harmony.api.main import app
from harmony.api.services.admin import JobManager
from harmony.services import ConversationService, PipelineConfig


@pytest.fixture
def job_manager() -> JobManager:
    return JobManager(pool=AsyncMock(), config_store=MagicMock())


@pytest.fixture
def mock_app_state() -> None:
    llm_service = MagicMock()
    prompt_manager = MagicMock()
    prompt_manager.render_system_prompt.return_value = "System prompt"
    search_service = AsyncMock()

    async def _stream_complete(
        *args: object, **kwargs: object
    ) -> AsyncGenerator[str, None]:
        yield "Mocked response"

    llm_service.stream_complete = _stream_complete
    prompt_manager.render_user_prompt.return_value = "User prompt"

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Mocked response"
    mock_response.choices[0].message.tool_calls = None
    llm_service.complete_with_tools = AsyncMock(return_value=mock_response)

    conversation_service = MagicMock(spec=ConversationService)
    conversation_service.create = AsyncMock(return_value="test-conversation-id")
    conversation_service.get_messages = AsyncMock(return_value=[])
    conversation_service.add_message = AsyncMock()
    conversation_service.add_tool_call = AsyncMock()
    conversation_service.add_tool_response = AsyncMock()
    conversation_service.add_trace = AsyncMock(return_value="trace-id")
    conversation_service.generate_title_async = AsyncMock(return_value=None)

    app.state.llm_service = llm_service
    app.state.conversation_service = conversation_service
    app.state.tool_registry = MagicMock()
    app.state.tool_registry.get_all_tools.return_value = []
    app.state.tool_registry.execute = AsyncMock(return_value="{}")
    app.state.prompt_manager = prompt_manager
    app.state.search_service = search_service
    app.state.es_service = AsyncMock()
    app.state.document_cache = MagicMock()
    app.state.service_config_store = AsyncMock()
    app.state.service_config_store.get = AsyncMock(return_value="0.5")
    app.state.settings = Settings(cors_allowed_origins="http://localhost")
    agents = AgentSuite(
        query_planner=QueryPlannerAgent(
            llm_service=llm_service, prompt_manager=prompt_manager
        ),
        searcher=SearcherAgent(search_service=search_service),
        critic=CriticAgent(llm_service=llm_service, prompt_manager=prompt_manager),
        synthesizer=SynthesizerAgent(
            llm_service=llm_service, prompt_manager=prompt_manager
        ),
    )
    app.state.orchestrator = AgenticOrchestrator(agents=agents)
    app.state.pipeline_config = PipelineConfig()
    app.state.config_store = MagicMock()
    app.state.job_manager = MagicMock()
    app.state.log_streamer = MagicMock()
    app.state.model_settings_store = MagicMock()
    app.state.model_policy_store = MagicMock()
    app.state.model_registry_service = AsyncMock()
    app.state.sso_handler = MagicMock()
    app.state.jwt_public_key = None
    app.state.auth_mode = "optional"
    app.state.redis_client = AsyncMock()
    app.state.model_policy_store = MagicMock()


@pytest.fixture
async def client(mock_app_state: None) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def conversation_service() -> MagicMock:
    return MagicMock(spec=ConversationService)


@pytest.fixture
def mock_llm(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock LLM calls to avoid real API calls.

    Patches both litellm.acompletion (for tests that call LLMService directly)
    and app.state.llm_service methods (for tests that go through the API).
    """
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Mocked response"
    mock_response.choices[0].message.tool_calls = None

    async def mock_acompletion(*args: object, **kwargs: object) -> MagicMock:
        return mock_response

    monkeypatch.setattr("harmony.services._llm.litellm.acompletion", mock_acompletion)

    async def _stream_complete(
        *args: object, **kwargs: object
    ) -> AsyncGenerator[str, None]:
        yield "Mocked response"

    monkeypatch.setattr(
        "harmony.services._llm.LLMService.complete_with_tools",
        AsyncMock(return_value=mock_response),
    )
    monkeypatch.setattr(
        "harmony.services._llm.LLMService.complete",
        AsyncMock(return_value=mock_response),
    )
    monkeypatch.setattr(
        "harmony.services._llm.LLMService.stream_complete", _stream_complete
    )
    return mock_response
