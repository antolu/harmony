from __future__ import annotations

import collections.abc
import typing
from typing import TYPE_CHECKING

import fastapi
import litellm

from harmony.api.services.admin._model_settings import ModelSettingsStore
from harmony.api.services.admin._service_config import ServiceConfigStore

if TYPE_CHECKING:
    from harmony.api.authz._context import AuthorizationContext
    from harmony.api.services.admin._model_policy import ModelPolicyStore


class LLMService:
    _LOCAL_PREFIXES: typing.ClassVar[tuple[str, ...]] = ("ollama/", "ollama_chat/")

    def __init__(
        self,
        *,
        service_config: ServiceConfigStore,
        model_policy_store: ModelPolicyStore | None = None,
    ) -> None:
        self._service_config = service_config
        self._model_policy_store = model_policy_store

    async def _resolve_model(self) -> str:
        return await ModelSettingsStore().get_llm_model()

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

    async def stream_complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        trace_id: str | None = None,
        agent_step: str | None = None,
        authz_context: AuthorizationContext | None = None,
        **kwargs: typing.Any,
    ) -> collections.abc.AsyncGenerator[str, None]:
        model = model or await self._resolve_model()
        await self._check_model_policy(model, authz_context)
        await self._assert_data_residency(model)

        completion_args: dict[str, typing.Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "metadata": {
                "trace_id": trace_id or "",
                "user_id": "",
                "endpoint": "",
                "agent_step": agent_step or "",
            },
        }
        api_base = await self._ollama_api_base(model)
        if api_base:
            completion_args["api_base"] = api_base
        if self._is_ollama(model):
            completion_args["extra_body"] = {"think": False}
        completion_args.update(kwargs)

        response = await litellm.acompletion(**completion_args)
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def complete(  # noqa: PLR0913
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        tools: list[dict[str, typing.Any]] | None = None,
        trace_id: str | None = None,
        agent_step: str | None = None,
        authz_context: AuthorizationContext | None = None,
        **kwargs: typing.Any,
    ) -> litellm.ModelResponse:
        model = model or await self._resolve_model()
        await self._check_model_policy(model, authz_context)
        await self._assert_data_residency(model)

        completion_args: dict[str, typing.Any] = {
            "model": model,
            "messages": messages,
            "metadata": {
                "trace_id": trace_id or "",
                "user_id": "",
                "endpoint": "",
                "agent_step": agent_step or "",
            },
        }

        if tools:
            completion_args["tools"] = tools
            completion_args["tool_choice"] = "auto"

        api_base = await self._ollama_api_base(model)
        if api_base:
            completion_args["api_base"] = api_base
        if self._is_ollama(model):
            completion_args["extra_body"] = {"think": False}
        completion_args.update(kwargs)

        return await litellm.acompletion(**completion_args)

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, typing.Any]],
        model: str | None = None,
    ) -> litellm.ModelResponse:
        return await self.complete(messages=messages, tools=tools, model=model)
