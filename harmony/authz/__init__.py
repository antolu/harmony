from __future__ import annotations

from harmony._mod_replace import replace_modname
from harmony.authz._context import AuthorizationContext
from harmony.authz._providers import (
    AuthorizationProvider,
    HarmonyRoleProvider,
    UrlDomainProvider,
)

replace_modname(AuthorizationContext, __name__)
replace_modname(AuthorizationProvider, __name__)
replace_modname(HarmonyRoleProvider, __name__)
replace_modname(UrlDomainProvider, __name__)

__all__ = [
    "AuthorizationContext",
    "AuthorizationProvider",
    "HarmonyRoleProvider",
    "UrlDomainProvider",
]
