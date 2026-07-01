from __future__ import annotations

import fnmatch
import typing

from harmony.authz._context import AuthorizationContext


class AuthorizationProvider(typing.Protocol):
    def get_acl_terms(self, context: AuthorizationContext) -> list[str]: ...


class HarmonyRoleProvider:
    def get_acl_terms(self, context: AuthorizationContext) -> list[str]:
        return list(context.harmony_roles)


class UrlDomainProvider:
    def __init__(self, pattern_roles: dict[str, list[str]]) -> None:
        self._pattern_roles = pattern_roles

    def get_acl_terms(self, context: AuthorizationContext) -> list[str]:
        url = str(context.raw_claims.get("request_url", ""))
        if not url:
            return []
        for pattern, roles in self._pattern_roles.items():
            if fnmatch.fnmatch(url, pattern):
                return list(roles)
        return []
