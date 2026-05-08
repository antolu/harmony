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
    from harmony.api.services.pipeline_config import PipelineConfig

    cfg = PipelineConfig()
    req = _make_request(pipeline_config=cfg)
    assert get_pipeline_config(req) is cfg
