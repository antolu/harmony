from __future__ import annotations

import collections.abc
import dataclasses
import re
import typing

import fastapi
import litellm
import pydantic

from harmony.api.services.admin._model_settings import ModelSettingsStore
from harmony.api.services.admin._service_config import ServiceConfigStore

if typing.TYPE_CHECKING:
    from harmony.api.authz._context import AuthorizationContext
    from harmony.api.services.admin._model_policy import ModelPolicyStore
    from harmony.api.services.admin._model_registry import ModelRegistryService

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


@dataclasses.dataclass
class LLMContext:
    trace_id: str | None = None
    agent_step: str | None = None
    authz_context: AuthorizationContext | None = None


async def _filter_think_tags(
    chunks: collections.abc.AsyncIterable[litellm.ModelResponse],
) -> collections.abc.AsyncGenerator[str, None]:
    buffer = ""
    in_think = False
    async for chunk in chunks:
        token = (
            chunk.choices[0].delta.content  # type: ignore[attr-defined]  # litellm streaming chunk stubs are incomplete
            if chunk.choices and chunk.choices[0].delta.content  # type: ignore[attr-defined]  # litellm streaming chunk stubs are incomplete
            else None
        )
        if not token:
            continue
        buffer += token
        if in_think:
            end = buffer.find("</think>")
            if end != -1:
                buffer = buffer[end + len("</think>") :]
                in_think = False
            else:
                buffer = ""
        else:
            start = buffer.find("<think>")
            if start != -1:
                yield buffer[:start]
                buffer = buffer[start + len("<think>") :]
                in_think = True
                end = buffer.find("</think>")
                if end != -1:
                    buffer = buffer[end + len("</think>") :]
                    in_think = False
                else:
                    buffer = ""
            else:
                yield buffer
                buffer = ""
    if buffer and not in_think:
        yield buffer


class LLMService:
    _LOCAL_PREFIXES: typing.ClassVar[tuple[str, ...]] = ("ollama/", "ollama_chat/")

    def __init__(
        self,
        *,
        service_config: ServiceConfigStore,
        model_settings_store: ModelSettingsStore,
        model_policy_store: ModelPolicyStore | None = None,
        model_registry: ModelRegistryService | None = None,
    ) -> None:
        self._service_config = service_config
        self._model_settings_store = model_settings_store
        self._model_policy_store = model_policy_store
        self._model_registry = model_registry

    def set_model_registry(self, registry: ModelRegistryService) -> None:
        self._model_registry = registry

    async def _resolve_model(self) -> str:
        return await self._model_settings_store.get_llm_model()

    async def _check_model_policy(
        self,
        model: str,
        authz_context: AuthorizationContext | None,
    ) -> None:
        if self._model_policy_store is None or authz_context is None:
            return
        allowed = await self._model_policy_store.get_allowed_roles(model)
        if not allowed:
            raise fastapi.HTTPException(
                status_code=403,
                detail=f"Model {model} has no access policy configured",
            )
        if not any(r in authz_context.harmony_roles for r in allowed):
            raise fastapi.HTTPException(
                status_code=403,
                detail=f"Model {model} is not permitted for this user role",
            )

    async def _assert_data_residency(self, model: str) -> None:
        flag = await self._service_config.get("data_residency_mode")
        if (
            flag
            and flag.lower() in {"true", "1", "yes"}
            and not any(model.startswith(p) for p in self._LOCAL_PREFIXES)
        ):
            msg = f"Data residency mode is enabled — external provider '{model}' is not permitted."
            raise RuntimeError(msg)

    def _is_ollama(self, model: str) -> bool:
        return any(model.startswith(p) for p in self._LOCAL_PREFIXES)

    async def _ollama_api_base(self, model: str) -> str | None:
        if self._is_ollama(model):
            return await self._service_config.get("ollama_host") or None
        return None

    async def _resolve_api_key(self, model: str) -> str | None:
        if self._model_registry is None or self._is_ollama(model):
            return None
        return await self._model_registry.resolve_api_key(model)

    async def stream_complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        ctx: LLMContext | None = None,
        **kwargs: pydantic.JsonValue,
    ) -> collections.abc.AsyncGenerator[str, None]:
        model = model or await self._resolve_model()
        ctx = ctx or LLMContext()
        await self._check_model_policy(model, ctx.authz_context)
        await self._assert_data_residency(model)

        completion_args: dict[str, pydantic.JsonValue] = {
            "model": model,
            "messages": typing.cast(pydantic.JsonValue, messages),
            "stream": True,
            "metadata": {
                "trace_id": ctx.trace_id or "",
                "user_id": "",
                "endpoint": "",
                "agent_step": ctx.agent_step or "",
            },
        }
        api_base = await self._ollama_api_base(model)
        if api_base:
            completion_args["api_base"] = api_base
        if self._is_ollama(model):
            completion_args["extra_body"] = {"think": False}
        api_key = await self._resolve_api_key(model)
        if api_key:
            completion_args["api_key"] = api_key
        completion_args.update(kwargs)

        response = await litellm.acompletion(**completion_args)
        async for chunk in _filter_think_tags(response):
            yield chunk

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        tools: list[dict[str, pydantic.JsonValue]] | None = None,
        ctx: LLMContext | None = None,
        **kwargs: pydantic.JsonValue,
    ) -> litellm.ModelResponse:
        model = model or await self._resolve_model()
        ctx = ctx or LLMContext()
        await self._check_model_policy(model, ctx.authz_context)
        await self._assert_data_residency(model)

        completion_args: dict[str, pydantic.JsonValue] = {
            "model": model,
            "messages": typing.cast(pydantic.JsonValue, messages),
            "metadata": {
                "trace_id": ctx.trace_id or "",
                "user_id": "",
                "endpoint": "",
                "agent_step": ctx.agent_step or "",
            },
        }

        if tools:
            kwargs["tools"] = typing.cast(pydantic.JsonValue, tools)
            completion_args["tool_choice"] = "auto"

        api_base = await self._ollama_api_base(model)
        if api_base:
            completion_args["api_base"] = api_base
        if self._is_ollama(model):
            completion_args["extra_body"] = {"think": False}
        api_key = await self._resolve_api_key(model)
        if api_key:
            completion_args["api_key"] = api_key
        completion_args.update(kwargs)

        result = await litellm.acompletion(**completion_args)
        if result.choices and result.choices[0].message.content:
            result.choices[0].message.content = _THINK_BLOCK_RE.sub(
                "", result.choices[0].message.content
            ).strip()
        return result

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, pydantic.JsonValue]],
        model: str | None = None,
    ) -> litellm.ModelResponse:
        return await self.complete(messages=messages, tools=tools, model=model)
