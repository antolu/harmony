from __future__ import annotations

import collections.abc
import typing

import litellm

from harmony.api.config import settings


class LLMService:
    def __init__(self) -> None:
        self.model = settings.llm_model

    async def stream_complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        **kwargs: typing.Any,
    ) -> collections.abc.AsyncGenerator[str, None]:
        model = model or self.model

        completion_args: dict[str, typing.Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        completion_args.update(kwargs)

        response = await litellm.acompletion(**completion_args)
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        tools: list[dict[str, typing.Any]] | None = None,
        **kwargs: typing.Any,
    ) -> typing.Any:
        model = model or self.model

        completion_args: dict[str, typing.Any] = {
            "model": model,
            "messages": messages,
        }

        if tools:
            completion_args["tools"] = tools
            completion_args["tool_choice"] = "auto"

        completion_args.update(kwargs)

        return await litellm.acompletion(**completion_args)

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, typing.Any]],
        model: str | None = None,
    ) -> typing.Any:
        return await self.complete(messages=messages, tools=tools, model=model)
