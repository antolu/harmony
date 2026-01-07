from __future__ import annotations

import json
import logging
import typing

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from harmony.api.tools.registry import Tool

logger = logging.getLogger(__name__)


class MCPTool:
    """Wrapper for MCP server tool that implements the Tool protocol."""

    def __init__(
        self, server_name: str, tool_def: dict[str, typing.Any], session: ClientSession
    ):
        """
        Initialize MCP tool wrapper.

        Args:
            server_name: Name of the MCP server providing this tool
            tool_def: Tool definition from MCP server
            session: MCP client session
        """
        self.server_name = server_name
        self.session = session
        self.name = tool_def["name"]
        self.description = tool_def.get("description", "")

        # Convert MCP input schema to our parameters format
        input_schema = tool_def.get("inputSchema", {})
        # Note: This is an instance variable (dynamic from MCP), not a class variable
        self.parameters: dict[str, typing.Any] = {  # type: ignore[misc]
            "type": "object",
            "properties": input_schema.get("properties", {}),
            "required": input_schema.get("required", []),
        }

    async def execute(self, *args: typing.Any, **kwargs: typing.Any) -> str:
        """
        Execute tool via MCP server.

        Args:
            **kwargs: Tool arguments

        Returns:
            JSON string of tool result
        """
        try:
            result = await self.session.call_tool(self.name, arguments=kwargs)

            # MCP returns a list of content items
            if result.content:
                # Combine all text content
                text_parts = [
                    item.text for item in result.content if hasattr(item, "text")
                ]

                combined_text = "\n".join(text_parts)

                return json.dumps({
                    "result": combined_text,
                    "server": self.server_name,
                    "tool": self.name,
                })

            return json.dumps({
                "result": "No content returned",
                "server": self.server_name,
            })

        except Exception as e:
            logger.exception(f"Error executing MCP tool {self.name}")
            return json.dumps({
                "error": str(e),
                "server": self.server_name,
                "tool": self.name,
            })


class MCPServerLoader:
    """Load and manage MCP servers."""

    def __init__(self, server_configs: list[dict[str, typing.Any]]):
        """
        Initialize MCP server loader.

        Args:
            server_configs: List of server configurations
        """
        self.server_configs = server_configs
        self.servers: dict[str, typing.Any] = {}
        self.sessions: dict[str, ClientSession] = {}
        self.tools: list[Tool] = []

    async def load_servers(self) -> None:
        """Load all MCP servers from config."""
        for server_config in self.server_configs:
            try:
                await self._load_server(server_config)
            except Exception:
                logger.exception(
                    f"Failed to load MCP server {server_config.get('name')}"
                )

    async def _load_server(self, config: dict[str, typing.Any]) -> None:
        """
        Load a single MCP server.

        Args:
            config: Server configuration with command, args, env
        """
        name = config.get("name", "unknown")
        command = config.get("command")
        args = config.get("args", [])
        env = config.get("env", {})

        if not command:
            logger.error(f"MCP server {name}: missing command")
            return

        logger.info(f"Loading MCP server: {name}")

        try:
            # Create server parameters
            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=env,
            )

            # Create stdio client context
            async with (
                stdio_client(server_params) as (read, write),
                ClientSession(read, write) as session,
            ):
                # Initialize the connection
                await session.initialize()

                # Store session
                self.sessions[name] = session

                # List available tools
                tools_result = await session.list_tools()

                # Create tool wrappers
                for tool_def in tools_result.tools:
                    mcp_tool = MCPTool(
                        server_name=name,
                        tool_def=tool_def.model_dump(),
                        session=session,
                    )
                    self.tools.append(mcp_tool)  # type: ignore[arg-type]
                    logger.info(f"Registered MCP tool: {mcp_tool.name} from {name}")

        except Exception:
            logger.exception(f"Failed to connect to MCP server {name}")

    def get_tools(self) -> list[Tool]:
        """Get all tools from all MCP servers."""
        return self.tools

    async def cleanup(self) -> None:
        """Clean up all MCP server connections."""
        for name, session in self.sessions.items():
            try:
                await session.close()
                logger.info(f"Closed MCP server: {name}")
            except Exception:
                logger.exception(f"Error closing MCP server {name}")
