from __future__ import annotations

import typing

import pydantic


class Tool(typing.Protocol):
    """Protocol for tool implementations.

    Note: parameters can be either a class variable (for static tools)
    or an instance variable (for dynamic MCP tools). Type checkers may
    complain about this flexibility, but it's intentional.
    """

    name: str
    description: str
    parameters: dict[str, pydantic.JsonValue]

    async def execute(self, *args: typing.Any, **kwargs: typing.Any) -> str:
        """Execute tool and return result as JSON string."""
        ...


class ToolRegistry:
    """Registry for all tools (built-in and MCP)."""

    def __init__(self) -> None:
        self.tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool in the registry."""
        self.tools[tool.name] = tool

    def get_tool(self, name: str) -> Tool | None:
        """Get tool by name."""
        return self.tools.get(name)

    def get_all_tools(self) -> list[dict[str, pydantic.JsonValue]]:
        """Get all tool definitions in OpenAI function calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self.tools.values()
        ]

    async def execute(self, name: str, args: dict[str, typing.Any]) -> str:
        """Execute a tool by name."""
        tool = self.get_tool(name)
        if not tool:
            return f'{{"error": "Unknown tool: {name}"}}'

        try:
            return await tool.execute(**args)
        except Exception as e:
            return f'{{"error": "{e!s}"}}'


# Global registry instance
tool_registry = ToolRegistry()
