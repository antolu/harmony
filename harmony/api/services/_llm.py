from __future__ import annotations

import collections.abc
import typing

import litellm

from harmony.api.config import settings
from harmony.api.services.admin._service_config import ServiceConfigStore


class LLMService:
    _LOCAL_PREFIXES: typing.ClassVar[tuple[str, ...]] = ("ollama/", "ollama_chat/")

    def __init__(self, *, service_config: ServiceConfigStore) -> None:
        self.model = settings.llm_model
        self._service_config = service_config

    async def _assert_data_residency(self, model: str) -> None:
        flag = await self._service_config.get("data_residency_mode")
        if (
            flag
            and flag.lower() in {"true", "1", "yes"}
            and not any(model.startswith(p) for p in self._LOCAL_PREFIXES)
        ):
            msg = f"Data residency mode is enabled — external provider '{model}' is not permitted."
            raise RuntimeError(msg)

    async def stream_complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        **kwargs: typing.Any,
    ) -> collections.abc.AsyncGenerator[str, None]:
        model = model or self.model
        await self._assert_data_residency(model)

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
    ) -> litellm.ModelResponse:
        model = model or self.model
        await self._assert_data_residency(model)

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
    ) -> litellm.ModelResponse:
        return await self.complete(messages=messages, tools=tools, model=model)
