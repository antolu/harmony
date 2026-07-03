from __future__ import annotations

import contextlib
import json
import logging
import typing

import pydantic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from harmony.models import StatusSinkProtocol

from ._registry import Tool

logger = logging.getLogger(__name__)


class MCPTool:
    """Wrapper for MCP server tool that implements the Tool protocol."""

    def __init__(
        self,
        server_name: str,
        tool_def: dict[str, pydantic.JsonValue],
        session: ClientSession,
    ) -> None:
        """
        Initialize MCP tool wrapper.

        Args:
            server_name: Name of the MCP server providing this tool
            tool_def: Tool definition from MCP server
            session: MCP client session
        """
        self.server_name = server_name
        self.session = session
        self.name = str(tool_def["name"])
        self.description = str(tool_def.get("description", ""))

        # Convert MCP input schema to our parameters format
        input_schema = typing.cast(
            dict[str, pydantic.JsonValue], tool_def.get("inputSchema", {})
        )
        # Note: This is an instance variable (dynamic from MCP), not a class variable
        self.parameters: dict[str, pydantic.JsonValue] = {  # type: ignore[misc]  # intentional deviation from Tool protocol for dynamic parameters
            "type": "object",
            "properties": input_schema.get("properties", {}),
            "required": input_schema.get("required", []),
        }

    async def execute(
        self, sink: StatusSinkProtocol, **kwargs: pydantic.JsonValue
    ) -> str:
        """
        Execute tool via MCP server.

        Args:
            **kwargs: Tool arguments

        Returns:
            JSON string of tool result
        """
        try:
            result = await self.session.call_tool(str(self.name), arguments=kwargs)

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
    """Load and manage MCP servers, keeping sessions alive for the application lifetime."""

    def __init__(self, server_configs: list[dict[str, pydantic.JsonValue]]) -> None:
        self.server_configs = server_configs
        self.tools: list[Tool] = []
        self._exit_stack = contextlib.AsyncExitStack()

    async def load_servers(self) -> None:
        """Load all MCP servers from config."""
        for server_config in self.server_configs:
            try:
                await self._load_server(server_config)
            except Exception:
                logger.exception(
                    f"Failed to load MCP server {server_config.get('name')}"
                )

    async def _load_server(self, config: dict[str, pydantic.JsonValue]) -> None:
        name = str(config.get("name", "unknown"))
        command = str(config.get("command", ""))
        args = typing.cast(list[str], config.get("args", []))
        env = typing.cast(dict[str, str], config.get("env", {}))

        if not command:
            logger.error(f"MCP server {name}: missing command")
            return

        logger.info(f"Loading MCP server: {name}")

        server_params = StdioServerParameters(command=command, args=args, env=env)

        read, write = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        session: ClientSession = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await session.initialize()

        tools_result = await session.list_tools()
        for tool_def in tools_result.tools:
            mcp_tool = MCPTool(
                server_name=str(name),
                tool_def=tool_def.model_dump(),
                session=session,
            )
            self.tools.append(mcp_tool)  # type: ignore[arg-type]  # mcp_tool intentionally implements parameters as instance variable rather than ClassVar
            logger.info(f"Registered MCP tool: {mcp_tool.name} from {name}")

    def get_tools(self) -> list[Tool]:
        return self.tools

    async def cleanup(self) -> None:
        """Close all MCP server connections."""
        await self._exit_stack.aclose()
        logger.info("Closed all MCP server connections")
