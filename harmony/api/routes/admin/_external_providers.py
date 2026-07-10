from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from harmony.models import AnonymousIdentity, UserIdentity
from harmony.services import SecretValueService
from harmony.services.admin import ServiceConfigStore

from ..._dependencies import (
    get_secret_service,
    get_service_config_store,
    require_role,
)

router = APIRouter()

_VALID_PROVIDERS = frozenset({"brave", "google"})
_ROLE_NAME_RE = re.compile(r"^[a-z_]+$")
_MAX_RESULTS_UPPER = 10
_MAX_RESULTS_LOWER = 1


class ExternalProviderStatus(BaseModel):
    provider: str
    enabled: bool
    has_key: bool
    max_results: int
    default_for_roles: dict[str, bool]


class ExternalProviderKeyBody(BaseModel):
    key: str


class ExternalProviderPatch(BaseModel):
    enabled: bool | None = None
    max_results: int | None = None
    default_for_roles: dict[str, bool] | None = None


async def _build_provider_status(
    provider: str,
    service_config: ServiceConfigStore,
    default_for_roles: dict[str, bool],
) -> ExternalProviderStatus:
    enabled_key = f"external_search_{provider}_enabled"
    key_config_key = f"{provider}_api_key"
    limit_key = f"external_search_{provider}_limit"

    enabled = await service_config.get(enabled_key) == "true"
    raw_key = await service_config.get(key_config_key)
    has_key = bool(raw_key)
    try:
        max_results = int(await service_config.get(limit_key))
    except (ValueError, TypeError):
        max_results = 5

    return ExternalProviderStatus(
        provider=provider,
        enabled=enabled,
        has_key=has_key,
        max_results=max_results,
        default_for_roles=default_for_roles,
    )


@router.get("/external-providers")
async def list_external_providers(
    service_config: ServiceConfigStore = Depends(get_service_config_store),
    _: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> list[ExternalProviderStatus]:
    default_for_roles = await service_config.get_external_search_defaults_for_roles()

    statuses = []
    for provider in ("brave", "google"):
        status = await _build_provider_status(
            provider, service_config, default_for_roles
        )
        statuses.append(status)
    return statuses


@router.post("/external-providers/{provider}/key", status_code=204)
async def set_provider_key(
    provider: str,
    body: ExternalProviderKeyBody,
    service_config: ServiceConfigStore = Depends(get_service_config_store),
    secret_service: SecretValueService = Depends(get_secret_service),
    _: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> Response:
    if provider not in _VALID_PROVIDERS:
        raise HTTPException(status_code=422, detail=f"Unknown provider: {provider}")

    key_name = f"{provider}_api_key"
    encrypted = secret_service.encrypt(body.key)
    await service_config.set(key_name, encrypted)
    return Response(status_code=204)


@router.patch("/external-providers/{provider}", status_code=204)
async def patch_provider(
    provider: str,
    body: ExternalProviderPatch,
    service_config: ServiceConfigStore = Depends(get_service_config_store),
    _: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> Response:
    if provider not in _VALID_PROVIDERS:
        raise HTTPException(status_code=422, detail=f"Unknown provider: {provider}")

    if body.enabled is not None:
        await service_config.set(
            f"external_search_{provider}_enabled", str(body.enabled).lower()
        )

    if body.max_results is not None:
        if not (_MAX_RESULTS_LOWER <= body.max_results <= _MAX_RESULTS_UPPER):
            raise HTTPException(
                status_code=422, detail="max_results must be between 1 and 10"
            )
        await service_config.set(
            f"external_search_{provider}_limit", str(body.max_results)
        )

    if body.default_for_roles is not None:
        for role, default_on in body.default_for_roles.items():
            if not _ROLE_NAME_RE.match(role):
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid role name: {role!r}. Role names must match [a-z_]+",
                )
            await service_config.set_external_search_default_for_role(
                role, default_on=default_on
            )

    return Response(status_code=204)
