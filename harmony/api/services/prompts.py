from __future__ import annotations

import typing
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


class PromptManager:
    """Manage prompt templates with variable injection."""

    def __init__(self, templates_dir: Path, auto_reload: bool = False):  # noqa: FBT001, FBT002
        """
        Initialize the prompt manager.

        Args:
            templates_dir: Directory containing prompt templates
            auto_reload: Enable hot-reloading of templates in development
        """
        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(),
            auto_reload=auto_reload,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(
        self,
        template_name: str,
        variables: dict[str, typing.Any] | None = None,
        include_builtins: bool = True,  # noqa: FBT001, FBT002
    ) -> str:
        """
        Render a prompt template with variables.

        Args:
            template_name: Template filename (e.g., "system/chat.md")
            variables: Custom variables to inject
            include_builtins: Include built-in variables (time, date)

        Returns:
            Rendered prompt text
        """
        template = self.env.get_template(template_name)

        context = variables.copy() if variables else {}

        if include_builtins:
            context.update(self._get_builtin_variables())

        return template.render(**context)

    def _get_builtin_variables(self) -> dict[str, typing.Any]:  # noqa: PLR6301
        """Get built-in variables for all prompts."""
        now = datetime.now()
        return {
            "current_date": now.strftime("%Y-%m-%d"),
            "current_time": now.strftime("%H:%M:%S"),
            "current_datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "day_of_week": now.strftime("%A"),
            "iso_timestamp": now.isoformat(),
        }

    def render_system_prompt(
        self,
        agent_name: str,
        variables: dict[str, typing.Any] | None = None,
    ) -> str:
        """
        Render a system prompt for an agent.

        Args:
            agent_name: Name of agent (chat, query_planner, etc.)
            variables: Additional context variables

        Returns:
            Rendered system prompt
        """
        return self.render(f"system/{agent_name}.md", variables)

    def render_user_prompt(
        self,
        prompt_name: str,
        variables: dict[str, typing.Any],
    ) -> str:
        """
        Render a user prompt template.

        Args:
            prompt_name: Name of user prompt template
            variables: Variables for the prompt

        Returns:
            Rendered user prompt
        """
        return self.render(f"user/{prompt_name}.md", variables)


# Global instance
prompt_manager: PromptManager | None = None


def get_prompt_manager() -> PromptManager:
    """Get the global prompt manager instance."""
    if prompt_manager is None:
        msg = "PromptManager not initialized"
        raise RuntimeError(msg)
    return prompt_manager


def initialize_prompt_manager(
    templates_dir: Path,
    auto_reload: bool = False,  # noqa: FBT001, FBT002
) -> None:
    """Initialize the global prompt manager."""
    global prompt_manager  # noqa: PLW0603
    prompt_manager = PromptManager(templates_dir, auto_reload)
