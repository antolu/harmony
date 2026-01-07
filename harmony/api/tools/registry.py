from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    pass


class Tool(typing.Protocol):
    """Protocol for tool implementations."""

    name: str
    description: str
    parameters: typing.ClassVar[dict[str, typing.Any]]

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

    def get_all_tools(self) -> list[dict[str, typing.Any]]:
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

    def generate_system_prompt(self) -> str:
        """Generate system prompt describing all available tools."""
        if not self.tools:
            return ""

        prompt = "You have access to the following tools:\n\n"

        for tool in self.tools.values():
            prompt += f"**{tool.name}**\n"
            prompt += f"  {tool.description}\n"

            # Add parameter descriptions
            if "properties" in tool.parameters:
                props = tool.parameters["properties"]
                required = tool.parameters.get("required", [])

                for param_name, param_def in props.items():
                    req_marker = (
                        " (required)" if param_name in required else " (optional)"
                    )
                    param_desc = param_def.get("description", "")
                    prompt += f"  - {param_name}{req_marker}: {param_desc}\n"

            prompt += "\n"

        prompt += (
            "Use these tools to help answer user questions. "
            "Always cite sources by mentioning URLs or document titles.\n"
        )

        return prompt


# Global registry instance
tool_registry = ToolRegistry()
