from __future__ import annotations

import json
import typing

from pydantic import JsonValue

from harmony.models import AnonymousIdentity, UserIdentity

if typing.TYPE_CHECKING:
    from harmony.api.services.admin import ModelPolicyStore, ModelRegistryService
    from harmony.services import ConversationService, LLMService


def sse_event(event: str, data: dict[str, JsonValue]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def resolve_and_authorize_model(
    model: str | None,
    current_user: UserIdentity | AnonymousIdentity,
    model_policy_store: ModelPolicyStore | None,
    model_registry_service: ModelRegistryService | None,
) -> tuple[str | None, str | None]:
    """Resolve a client model id to its full litellm form and check role policy.

    Returns ``(resolved_model, error_event)``. When ``error_event`` is non-None it is
    a ready-to-yield SSE ``error`` string and ``resolved_model`` is None; callers should
    yield it and stop. Shared by every streaming search endpoint so model resolution and
    authorization stay identical across them.
    """
    if model is None:
        return None, sse_event("error", {"message": "No model selected"})

    resolved_model: str | None = None
    if model_registry_service is not None:
        resolved_model = await model_registry_service.resolve_litellm_model_id(model)
    if resolved_model is None:
        resolved_model = model

    if isinstance(current_user, UserIdentity) and model_policy_store is not None:
        allowed_roles = await model_policy_store.get_allowed_roles(resolved_model)
        if allowed_roles and current_user.harmony_role not in allowed_roles:
            return None, sse_event(
                "error", {"message": "Model not permitted for your role"}
            )

    return resolved_model, None


def user_id_of(current_user: UserIdentity | AnonymousIdentity) -> str | None:
    return current_user.id if isinstance(current_user, UserIdentity) else None


async def maybe_generate_title_event(  # noqa: PLR0913
    *,
    is_new_conversation: bool,
    conversation_id: str,
    user_id: str | None,
    query: str,
    answer: str,
    conversation_service: ConversationService,
    llm_service: LLMService,
) -> str | None:
    """Generate a conversation title for a new conversation and return its SSE event.

    Returns a ready-to-yield ``title`` event string, or None when no title was
    produced (existing conversation, empty answer, or generation failed/declined).
    """
    if not (is_new_conversation and answer):
        return None
    title = await conversation_service.generate_title_async(
        conversation_id, user_id, query, answer, llm_service
    )
    if not title:
        return None
    return sse_event("title", {"conversation_id": conversation_id, "title": title})
