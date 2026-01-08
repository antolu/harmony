"""Tests for prompt template system."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest

from harmony.api.services.prompts import (
    PromptManager,
    get_prompt_manager,
    initialize_prompt_manager,
)


@pytest.fixture
def prompts_dir() -> Path:
    """Get path to prompts directory."""
    return Path(__file__).parent.parent / "harmony" / "prompts"


@pytest.fixture
def prompt_manager(prompts_dir: Path) -> PromptManager:
    """Create a PromptManager instance."""
    return PromptManager(prompts_dir, auto_reload=False)


def test_initialization(prompts_dir: Path) -> None:
    """Test PromptManager initialization."""
    pm = PromptManager(prompts_dir, auto_reload=True)
    assert pm.templates_dir == prompts_dir
    assert pm.env.auto_reload is True


def test_builtin_variables(prompt_manager: PromptManager) -> None:
    """Test built-in variable generation."""
    variables = prompt_manager._get_builtin_variables()

    assert "current_date" in variables
    assert "current_time" in variables
    assert "current_datetime" in variables
    assert "day_of_week" in variables
    assert "iso_timestamp" in variables

    assert re.match(r"\d{4}-\d{2}-\d{2}", variables["current_date"])
    assert re.match(r"\d{2}:\d{2}:\d{2}", variables["current_time"])
    assert variables["day_of_week"] in {
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    }


def test_render_basic(prompt_manager: PromptManager) -> None:
    """Test basic template rendering."""
    result = prompt_manager.render("system/query_planner.md", include_builtins=False)

    assert "search query planner" in result
    assert "diverse search queries" in result


def test_render_with_builtins(prompt_manager: PromptManager) -> None:
    """Test rendering with built-in variables."""
    result = prompt_manager.render("system/query_planner.md", include_builtins=True)

    today = datetime.now().strftime("%Y-%m-%d")
    assert today in result


def test_render_with_custom_variables(prompt_manager: PromptManager) -> None:
    """Test rendering with custom variables."""
    result = prompt_manager.render(
        "user/query_plan.md",
        {"user_query": "What is photosynthesis?", "context": "Biology"},
        include_builtins=False,
    )

    assert "What is photosynthesis?" in result
    assert "Biology" in result


def test_render_system_prompt(prompt_manager: PromptManager) -> None:
    """Test render_system_prompt convenience method."""
    result = prompt_manager.render_system_prompt("critic")

    assert "critical reviewer" in result
    assert "Factual accuracy" in result


def test_render_user_prompt(prompt_manager: PromptManager) -> None:
    """Test render_user_prompt convenience method."""
    result = prompt_manager.render_user_prompt(
        "synthesize",
        {
            "user_query": "Test question",
            "sources": [
                {
                    "title": "Source 1",
                    "url": "http://example.com",
                    "content": "Test content",
                }
            ],
        },
    )

    assert "Test question" in result
    assert "Source 1" in result
    assert "http://example.com" in result


def test_initialize_and_get(tmp_path: Path) -> None:
    """Test initializing and getting global instance."""
    system_dir = tmp_path / "system"
    system_dir.mkdir()
    (system_dir / "test.md").write_text("Test template")

    initialize_prompt_manager(tmp_path, auto_reload=True)

    pm = get_prompt_manager()
    assert pm is not None
    assert pm.templates_dir == tmp_path
    assert pm.env.auto_reload is True


def test_get_before_initialize_raises() -> None:
    """Test that getting manager before initialization raises error."""
    import harmony.api.services.prompts as prompts_module  # noqa: PLC0415 - inline import to reset module state

    prompts_module.prompt_manager = None

    with pytest.raises(RuntimeError, match="PromptManager not initialized"):
        get_prompt_manager()


def test_chat_template(prompt_manager: PromptManager) -> None:
    """Test chat system template."""
    result = prompt_manager.render_system_prompt(
        "chat",
        {
            "tools": [
                {
                    "name": "test_tool",
                    "description": "Test tool description",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "arg1": {"type": "string", "description": "Argument 1"}
                        },
                        "required": ["arg1"],
                    },
                }
            ]
        },
    )

    assert "helpful research assistant" in result
    assert "test_tool" in result
    assert "Test tool description" in result
    assert "arg1" in result
    assert "required" in result


def test_chat_template_no_tools(prompt_manager: PromptManager) -> None:
    """Test chat template with no tools."""
    result = prompt_manager.render_system_prompt("chat", {"tools": []})

    assert "helpful research assistant" in result
    assert "test_tool" not in result


def test_query_planner_template(prompt_manager: PromptManager) -> None:
    """Test query planner system template."""
    result = prompt_manager.render_system_prompt("query_planner")

    assert "search query planner" in result
    assert "diverse search queries" in result
    assert "varied terminology" in result


def test_synthesizer_template(prompt_manager: PromptManager) -> None:
    """Test synthesizer system template."""
    result = prompt_manager.render_system_prompt("synthesizer")

    assert "research synthesizer" in result
    assert "well-cited answers" in result
    assert "Cite sources appropriately" in result


def test_critic_template(prompt_manager: PromptManager) -> None:
    """Test critic system template."""
    result = prompt_manager.render_system_prompt("critic")

    assert "critical reviewer" in result
    assert "Factual accuracy" in result
    assert "Completeness" in result


def test_query_plan_template(prompt_manager: PromptManager) -> None:
    """Test query planning user template."""
    result = prompt_manager.render_user_prompt(
        "query_plan", {"user_query": "What is AI?"}
    )

    assert "What is AI?" in result
    assert "JSON array" in result
    assert "diverse search queries" in result


def test_query_plan_with_context(prompt_manager: PromptManager) -> None:
    """Test query planning with context."""
    result = prompt_manager.render_user_prompt(
        "query_plan", {"user_query": "What is AI?", "context": "Machine learning"}
    )

    assert "What is AI?" in result
    assert "Machine learning" in result


def test_synthesize_template(prompt_manager: PromptManager) -> None:
    """Test synthesis user template."""
    sources = [
        {
            "title": "Source 1",
            "url": "http://example.com/1",
            "content": "Content about AI and machine learning.",
        },
        {
            "title": "Source 2",
            "url": "http://example.com/2",
            "snippet": "More information on neural networks.",
        },
    ]

    result = prompt_manager.render_user_prompt(
        "synthesize", {"user_query": "What is AI?", "sources": sources}
    )

    assert "What is AI?" in result
    assert "[1] Source 1" in result
    assert "http://example.com/1" in result
    assert "[2] Source 2" in result
    assert "Content about AI" in result


def test_synthesize_refine_template(prompt_manager: PromptManager) -> None:
    """Test refinement synthesis template."""
    critique = {
        "issues": ["Issue 1", "Issue 2"],
        "suggestions": ["Suggestion 1", "Suggestion 2"],
        "factual_accuracy": 0.7,
        "completeness": 0.6,
        "hallucination_risk": 0.3,
    }

    sources = [{"title": "Source", "url": "http://example.com", "content": "Text"}]

    result = prompt_manager.render_user_prompt(
        "synthesize_refine",
        {
            "user_query": "What is AI?",
            "previous_draft": "Initial answer about AI.",
            "critique": critique,
            "sources": sources,
        },
    )

    assert "What is AI?" in result
    assert "Initial answer about AI" in result
    assert "Issue 1" in result
    assert "Suggestion 1" in result
    assert "70.0%" in result
    assert "60.0%" in result


def test_critique_template(prompt_manager: PromptManager) -> None:
    """Test critique user template."""
    sources = [
        {"title": "Source 1", "content": "Content 1"},
        {"title": "Source 2", "snippet": "Snippet 2"},
    ]

    result = prompt_manager.render_user_prompt(
        "critique",
        {
            "user_query": "What is AI?",
            "draft": "AI is artificial intelligence.",
            "sources": sources,
        },
    )

    assert "What is AI?" in result
    assert "AI is artificial intelligence" in result
    assert "Source 1" in result
    assert "factual_accuracy" in result
    assert "consensus_reached" in result


def test_builtin_variables_injected(prompt_manager: PromptManager) -> None:
    """Test that built-in variables are automatically injected."""
    result = prompt_manager.render("system/query_planner.md")

    today = datetime.now().strftime("%Y-%m-%d")
    assert today in result


def test_disable_builtins(prompt_manager: PromptManager) -> None:
    """Test disabling built-in variable injection."""
    result = prompt_manager.render("system/query_planner.md", include_builtins=False)

    assert "search query planner" in result


def test_jinja2_filters(prompt_manager: PromptManager) -> None:
    """Test that Jinja2 filters work in templates."""
    max_content_len = 2000
    sources = [
        {
            "title": "Very long title " + "x" * 1000,
            "url": "http://example.com",
            "content": "Very long content " + "y" * max_content_len,
        }
    ]

    result = prompt_manager.render_user_prompt(
        "synthesize", {"user_query": "Test", "sources": sources}
    )

    assert len(result) < max_content_len


def test_jinja2_loops(prompt_manager: PromptManager) -> None:
    """Test that Jinja2 loops work in templates."""
    sources = [
        {
            "title": f"Source {i}",
            "url": f"http://example.com/{i}",
            "content": "Text",
        }
        for i in range(5)
    ]

    result = prompt_manager.render_user_prompt(
        "synthesize", {"user_query": "Test", "sources": sources}
    )

    assert "[1]" in result
    assert "[2]" in result
    assert "[5]" in result


def test_missing_variable_handled_gracefully(prompt_manager: PromptManager) -> None:
    """Test that missing variables are handled gracefully by Jinja2."""
    result = prompt_manager.render_user_prompt(
        "synthesize", {"sources": [], "user_query": "Test"}
    )
    assert "Test" in result
