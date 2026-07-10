"""Tests for prompt template system."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest

from harmony.services import PromptManager


@pytest.fixture
def templates_dir() -> Path:
    """Get path to the harmony/ package root, used as the Jinja search root."""
    return Path(__file__).parent.parent.parent / "harmony"


@pytest.fixture
def prompt_manager(templates_dir: Path) -> PromptManager:
    """Create a PromptManager instance."""
    return PromptManager(templates_dir, auto_reload=False)


def test_initialization(templates_dir: Path) -> None:
    """Test PromptManager initialization."""
    pm = PromptManager(templates_dir, auto_reload=True)
    assert pm.templates_dir == templates_dir
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
    result = prompt_manager.render(
        "agents/foa/prompts/system_query_planner.md", include_builtins=False
    )

    assert "search query planner" in result
    assert "semantic query" in result
    assert "keyword variants" in result


def test_render_with_builtins(prompt_manager: PromptManager) -> None:
    """Test rendering with built-in variables."""
    result = prompt_manager.render(
        "agents/foa/prompts/system_query_planner.md", include_builtins=True
    )

    today = datetime.now().strftime("%Y-%m-%d")
    assert today in result


def test_render_with_custom_variables(prompt_manager: PromptManager) -> None:
    """Test rendering with custom variables."""
    result = prompt_manager.render(
        "agents/foa/prompts/user_query_plan.md",
        {"user_query": "What is photosynthesis?", "context": "Biology"},
        include_builtins=False,
    )

    assert "What is photosynthesis?" in result
    assert "Biology" in result


def test_render_system_prompt(prompt_manager: PromptManager) -> None:
    """Test rendering a system prompt template."""
    result = prompt_manager.render("agents/foa/prompts/system_critic.md")

    assert "critical reviewer" in result
    assert "Factual accuracy" in result


def test_render_user_prompt(prompt_manager: PromptManager) -> None:
    """Test rendering a user prompt template."""
    result = prompt_manager.render(
        "agents/foa/prompts/user_synthesize.md",
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


def test_chat_template(prompt_manager: PromptManager) -> None:
    """Test chat system template."""
    result = prompt_manager.render(
        "agents/simple/prompts/system_chat.md",
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
    result = prompt_manager.render(
        "agents/simple/prompts/system_chat.md", {"tools": []}
    )

    assert "helpful research assistant" in result
    assert "test_tool" not in result


def test_query_planner_template(prompt_manager: PromptManager) -> None:
    """Test query planner system template."""
    result = prompt_manager.render("agents/foa/prompts/system_query_planner.md")

    assert "search query planner" in result
    assert "semantic query" in result
    assert "keyword variants" in result


def test_synthesizer_template(prompt_manager: PromptManager) -> None:
    """Test synthesizer system template."""
    result = prompt_manager.render("agents/foa/prompts/system_synthesizer.md")

    assert "research synthesizer" in result
    assert "well-cited answers" in result
    assert "Cite sources appropriately" in result


def test_critic_template(prompt_manager: PromptManager) -> None:
    """Test critic system template."""
    result = prompt_manager.render("agents/foa/prompts/system_critic.md")

    assert "critical reviewer" in result
    assert "Factual accuracy" in result
    assert "Completeness" in result


def test_query_plan_template(prompt_manager: PromptManager) -> None:
    """Test query planning user template."""
    result = prompt_manager.render(
        "agents/foa/prompts/user_query_plan.md", {"user_query": "What is AI?"}
    )

    assert "What is AI?" in result
    assert "JSON object" in result
    assert "semantic_query" in result
    assert "keyword_variants" in result


def test_query_plan_with_context(prompt_manager: PromptManager) -> None:
    """Test query planning with context."""
    result = prompt_manager.render(
        "agents/foa/prompts/user_query_plan.md",
        {"user_query": "What is AI?", "context": "Machine learning"},
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

    result = prompt_manager.render(
        "agents/foa/prompts/user_synthesize.md",
        {"user_query": "What is AI?", "sources": sources},
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

    result = prompt_manager.render(
        "agents/foa/prompts/user_synthesize_refine.md",
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

    result = prompt_manager.render(
        "agents/foa/prompts/user_critique.md",
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
    result = prompt_manager.render("agents/foa/prompts/system_query_planner.md")

    today = datetime.now().strftime("%Y-%m-%d")
    assert today in result


def test_disable_builtins(prompt_manager: PromptManager) -> None:
    """Test disabling built-in variable injection."""
    result = prompt_manager.render(
        "agents/foa/prompts/system_query_planner.md", include_builtins=False
    )

    assert "search query planner" in result


def test_synthesize_renders_full_content(prompt_manager: PromptManager) -> None:
    """Synthesize no longer truncates source content.

    Budget governance moved to SourcePool.select_within_budget in Python; the
    template renders whatever pre-budgeted content it receives, in full.
    """
    long_content = "Very long content " + "y" * 2000
    sources = [
        {
            "title": "A title",
            "url": "http://example.com",
            "content": long_content,
        }
    ]

    result = prompt_manager.render(
        "agents/foa/prompts/user_synthesize.md",
        {"user_query": "Test", "sources": sources},
    )

    assert long_content in result


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

    result = prompt_manager.render(
        "agents/foa/prompts/user_synthesize.md",
        {"user_query": "Test", "sources": sources},
    )

    assert "[1]" in result
    assert "[2]" in result
    assert "[5]" in result


def test_missing_variable_handled_gracefully(prompt_manager: PromptManager) -> None:
    """Test that missing variables are handled gracefully by Jinja2."""
    result = prompt_manager.render(
        "agents/foa/prompts/user_synthesize.md",
        {"sources": [], "user_query": "Test"},
    )
    assert "Test" in result


@pytest.mark.parametrize(
    "template_path",
    [
        "agents/foa/prompts/system_critic.md",
        "agents/foa/prompts/system_query_planner.md",
        "agents/foa/prompts/system_synthesizer.md",
    ],
)
def test_system_prompts_extend_base(
    prompt_manager: PromptManager, template_path: str
) -> None:
    """foa system prompts inherit the shared 'Current date' line from _base_prompt.md."""
    result = prompt_manager.render(template_path)

    today = datetime.now().strftime("%Y-%m-%d")
    assert f"Current date: {today}" in result


def test_chat_extends_base_and_includes_current_time(
    prompt_manager: PromptManager,
) -> None:
    """The chat prompt extends the base template and adds current_time via its own block."""
    result = prompt_manager.render(
        "agents/simple/prompts/system_chat.md", {"tools": []}
    )

    today = datetime.now().strftime("%Y-%m-%d")
    assert f"Current date: {today}" in result
    assert "Current time:" in result


@pytest.mark.parametrize(
    ("template_path", "variables"),
    [
        (
            "agents/foa/prompts/system_synthesizer.md",
            None,
        ),
        (
            "agents/foa/prompts/user_synthesize.md",
            {"user_query": "Test", "sources": []},
        ),
        (
            "agents/foa/prompts/user_synthesize_refine.md",
            {
                "user_query": "Test",
                "previous_draft": "Draft",
                "critique": {},
                "sources": [],
            },
        ),
    ],
)
def test_shared_citation_format_included(
    prompt_manager: PromptManager,
    template_path: str,
    variables: dict[str, object] | None,
) -> None:
    """Templates that include _citation_format.md render its shared instruction text."""
    result = prompt_manager.render(template_path, variables)

    assert "e.g. [2,5]" in result
