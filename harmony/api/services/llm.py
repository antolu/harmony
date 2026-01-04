from __future__ import annotations

import os
import typing

from litellm import completion

from harmony.api.config import settings


class LLMService:
    def __init__(self) -> None:
        # Set API keys
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key

    @staticmethod
    def complete(
        messages: list[dict[str, str]],
        model: str | None = None,
        tools: list[dict[str, typing.Any]] | None = None,
        **kwargs: typing.Any,
    ) -> typing.Any:
        """
        Call LLM with messages and optional tools.

        Args:
            messages: List of message dicts with role and content
            model: Model name (default from settings)
            tools: List of tool definitions for function calling
            **kwargs: Additional arguments for litellm.completion()

        Returns:
            LiteLLM completion response
        """
        model = model or settings.llm_model

        completion_args: dict[str, typing.Any] = {
            "model": model,
            "messages": messages,
        }

        if tools:
            completion_args["tools"] = tools
            completion_args["tool_choice"] = "auto"

        completion_args.update(kwargs)

        return completion(**completion_args)

    @staticmethod
    def complete_with_tools(
        messages: list[dict[str, str]],
        tools: list[dict[str, typing.Any]],
        model: str | None = None,
    ) -> typing.Any:
        """
        Call LLM with function calling support.

        Args:
            messages: Conversation history
            tools: Tool definitions
            model: Model name

        Returns:
            LiteLLM completion response with tool calls
        """
        return LLMService.complete(messages=messages, tools=tools, model=model)


# Global instance
llm_service = LLMService()
