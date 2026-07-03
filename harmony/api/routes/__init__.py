# ruff: noqa: RUF067
from __future__ import annotations

import fastapi

from .._health import router as health_router
from ..routes import _agentic_search, _search, _simple_chat, _user_auth
from ..routes import _conversations as conversations_route
from ..routes import _feedback as feedback_route
from ..routes import _preferences as preferences_route
from ..routes import _settings as settings_route
from ..routes.admin import (
    _audit_log as audit_log_route,
)
from ..routes.admin import (
    _auth,
    _configs,
    _crawler_sessions,
    _data_sources,
    _index_config,
    _infrastructure,
    _jobs,
    _logs,
    _ollama,
    _reset,
    _safety,
    _schema,
    _setup,
    _signals,
    _stats,
    _vllm,
    _webhook_internal,
)
from ..routes.admin import (
    _export as export_route,
)
from ..routes.admin import (
    _external_providers as external_providers_route,
)
from ..routes.admin import (
    _llm_api_keys as llm_api_keys_route,
)
from ..routes.admin import (
    _model_hosts as model_hosts_route,
)
from ..routes.admin import (
    _model_policy as model_policy_route,
)
from ..routes.admin import (
    _model_settings as model_settings_route,
)
from ..routes.admin import (
    _schedules as schedules_route,
)
from ..routes.admin import (
    _token_usage as token_usage_route,
)
from ..routes.admin import (
    _urls as urls_route,
)
from ..routes.admin import (
    _users as users_route,
)
from ..routes.admin import (
    _webhooks as webhooks_route,
)

router = fastapi.APIRouter()

router.include_router(_search.router, prefix="/api")
router.include_router(_simple_chat.router, prefix="/api")
router.include_router(_agentic_search.router, prefix="/api")
router.include_router(settings_route.router, prefix="/api")
router.include_router(health_router)

router.include_router(_user_auth.router, prefix="/api", tags=["user-auth"])
router.include_router(_schema.router, prefix="/api/admin/configs", tags=["schema"])
router.include_router(_configs.router, prefix="/api/admin/configs", tags=["configs"])
router.include_router(
    _data_sources.router, prefix="/api/admin/data-sources", tags=["admin"]
)
router.include_router(_jobs.router, prefix="/api/admin/jobs", tags=["jobs"])
router.include_router(_logs.router, prefix="/api/admin/jobs", tags=["logs"])
router.include_router(_reset.router, prefix="/api/reset", tags=["reset"])
router.include_router(_auth.router, prefix="/api/auth", tags=["auth"])
router.include_router(_safety.router, prefix="/api/internal", tags=["internal"])
router.include_router(
    _crawler_sessions.router, prefix="/api/internal", tags=["internal"]
)
router.include_router(_stats.router, prefix="/api/internal", tags=["internal"])
router.include_router(_signals.router, prefix="/api/internal", tags=["internal"])
router.include_router(
    _webhook_internal.router, prefix="/api/internal", tags=["internal"]
)
router.include_router(_setup.router, prefix="/api/setup", tags=["setup"])
router.include_router(
    _index_config.router, prefix="/api/index-config", tags=["index-config"]
)
router.include_router(
    _ollama.router, prefix="/api/admin/models/ollama", tags=["ollama"]
)
router.include_router(_vllm.router, prefix="/api/admin/models/vllm", tags=["vllm"])
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
