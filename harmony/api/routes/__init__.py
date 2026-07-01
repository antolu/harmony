# ruff: noqa: RUF067
from __future__ import annotations

import fastapi

from harmony.api._health import router as health_router
from harmony.api.routes import agentic_search, chat, search, user_auth
from harmony.api.routes import conversations as conversations_route
from harmony.api.routes import feedback as feedback_route
from harmony.api.routes import preferences as preferences_route
from harmony.api.routes import settings as settings_route
from harmony.api.routes.admin import (
    _crawler_sessions,
    _infrastructure,
    _safety,
    _signals,
    _stats,
    _webhook_internal,
    auth,
    configs,
    data_sources,
    index_config,
    jobs,
    logs,
    ollama,
    reset,
    schema,
    setup,
    vllm,
)
from harmony.api.routes.admin import (
    audit_log as audit_log_route,
)
from harmony.api.routes.admin import (
    export as export_route,
)
from harmony.api.routes.admin import (
    external_providers as external_providers_route,
)
from harmony.api.routes.admin import (
    llm_api_keys as llm_api_keys_route,
)
from harmony.api.routes.admin import (
    model_hosts as model_hosts_route,
)
from harmony.api.routes.admin import (
    model_policy as model_policy_route,
)
from harmony.api.routes.admin import (
    model_settings as model_settings_route,
)
from harmony.api.routes.admin import (
    schedules as schedules_route,
)
from harmony.api.routes.admin import (
    token_usage as token_usage_route,
)
from harmony.api.routes.admin import (
    urls as urls_route,
)
from harmony.api.routes.admin import (
    users as users_route,
)
from harmony.api.routes.admin import (
    webhooks as webhooks_route,
)

router = fastapi.APIRouter()

router.include_router(search.router, prefix="/api")
router.include_router(chat.router, prefix="/api")
router.include_router(agentic_search.router, prefix="/api")
router.include_router(settings_route.router, prefix="/api")
router.include_router(health_router)

router.include_router(user_auth.router, prefix="/api", tags=["user-auth"])
router.include_router(schema.router, prefix="/api/admin/configs", tags=["schema"])
router.include_router(configs.router, prefix="/api/admin/configs", tags=["configs"])
router.include_router(
    data_sources.router, prefix="/api/admin/data-sources", tags=["admin"]
)
router.include_router(jobs.router, prefix="/api/admin/jobs", tags=["jobs"])
router.include_router(logs.router, prefix="/api/admin/jobs", tags=["logs"])
router.include_router(reset.router, prefix="/api/reset", tags=["reset"])
router.include_router(auth.router, prefix="/api/auth", tags=["auth"])
router.include_router(_safety.router, prefix="/api/internal", tags=["internal"])
router.include_router(
    _crawler_sessions.router, prefix="/api/internal", tags=["internal"]
)
router.include_router(_stats.router, prefix="/api/internal", tags=["internal"])
router.include_router(_signals.router, prefix="/api/internal", tags=["internal"])
router.include_router(
    _webhook_internal.router, prefix="/api/internal", tags=["internal"]
)
router.include_router(setup.router, prefix="/api/setup", tags=["setup"])
router.include_router(
    index_config.router, prefix="/api/index-config", tags=["index-config"]
)
router.include_router(ollama.router, prefix="/api/admin/models/ollama", tags=["ollama"])
router.include_router(vllm.router, prefix="/api/admin/models/vllm", tags=["vllm"])
router.include_router(
    model_settings_route.router, prefix="/api/admin/models", tags=["model-settings"]
)
router.include_router(
    model_hosts_route.router,
    prefix="/api/admin/model-hosts",
    tags=["admin/model-hosts"],
)
router.include_router(
    llm_api_keys_route.router,
    prefix="/api/admin/llm-api-keys",
    tags=["admin/llm-api-keys"],
)
router.include_router(
    token_usage_route.router, prefix="/api/admin", tags=["token-usage"]
)
router.include_router(urls_route.router, prefix="/api")
router.include_router(users_route.router, prefix="/api")
router.include_router(
    model_policy_route.router, prefix="/api/settings", tags=["model-policy"]
)
router.include_router(
    external_providers_route.router, prefix="/api/settings", tags=["external-providers"]
)
router.include_router(_infrastructure.router, prefix="/api", tags=["admin"])
router.include_router(
    conversations_route.router, prefix="/api/conversations", tags=["conversations"]
)
router.include_router(feedback_route.router, prefix="/api/feedback", tags=["feedback"])
router.include_router(
    preferences_route.router, prefix="/api/preferences", tags=["preferences"]
)
router.include_router(audit_log_route.router, prefix="/api")
router.include_router(webhooks_route.router, prefix="/api")
router.include_router(schedules_route.router, prefix="/api")
router.include_router(export_route.router, prefix="/api")

__all__ = ["router"]
