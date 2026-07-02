from __future__ import annotations

import collections.abc
import contextlib
import contextvars
import dataclasses
import re
import typing

import litellm
import pydantic

from harmony.api.exceptions import PermissionDeniedError
from harmony.authz._context import AuthorizationContext

from .admin._model_policy import ModelPolicyStore
from .admin._model_registry import ModelRegistryService
from .admin._service_config import ConfigProvider

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

current_model: contextvars.ContextVar[str] = contextvars.ContextVar("current_model")


@contextlib.contextmanager
def use_model(model: str) -> collections.abc.Iterator[None]:
    """Scope the active LLM model for every completion call made within the block."""
    token = current_model.set(model)
    try:
        yield
    finally:
        current_model.reset(token)


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
        service_config: ConfigProvider,
        model_policy_store: ModelPolicyStore | None = None,
        model_registry: ModelRegistryService | None = None,
    ) -> None:
        self._service_config = service_config
        self._model_policy_store = model_policy_store
        self._model_registry = model_registry

    def set_model_registry(self, registry: ModelRegistryService) -> None:
        self._model_registry = registry

    async def _check_model_policy(
        self,
        model: str,
        authz_context: AuthorizationContext | None,
    ) -> None:
        if self._model_policy_store is None or authz_context is None:
            return
        allowed = await self._model_policy_store.get_allowed_roles(model)
        if not allowed:
            msg = f"Model {model} has no access policy configured"
            raise PermissionDeniedError(msg)
        if not any(r in authz_context.harmony_roles for r in allowed):
            msg = f"Model {model} is not permitted for this user role"
            raise PermissionDeniedError(msg)

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

    async def _resolve(self, model: str) -> tuple[str | None, str | None]:
        if self._model_registry is None:
            return None, None
        row = await self._model_registry.get_by_litellm_id(model)
        if row is None:
            return None, None
        conn = await self._model_registry.resolve_connection(row.id)
        return conn.api_base, conn.api_key

    async def stream_complete(
        self,
        messages: list[dict[str, str]],
        ctx: LLMContext | None = None,
        **kwargs: pydantic.JsonValue,
    ) -> collections.abc.AsyncGenerator[str, None]:
        model = current_model.get(None)
        if not model:
            msg = "No active LLM model. Use use_model() context manager."
            raise RuntimeError(msg)
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
        api_base, api_key = await self._resolve(model)
        if api_base:
            completion_args["api_base"] = api_base
        if self._is_ollama(model):
            completion_args["extra_body"] = {"think": False}
        if api_key:
            completion_args["api_key"] = api_key
        completion_args.update(kwargs)

        response = await litellm.acompletion(**completion_args)
        async for chunk in _filter_think_tags(response):
            yield chunk

    async def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, pydantic.JsonValue]] | None = None,
        ctx: LLMContext | None = None,
        **kwargs: pydantic.JsonValue,
    ) -> litellm.ModelResponse:
        model = current_model.get(None)
        if not model:
            msg = "No active LLM model. Use use_model() context manager."
            raise RuntimeError(msg)
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

        api_base, api_key = await self._resolve(model)
        if api_base:
            completion_args["api_base"] = api_base
        if self._is_ollama(model):
            completion_args["extra_body"] = {"think": False}
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
    ) -> litellm.ModelResponse:
        return await self.complete(messages=messages, tools=tools)
