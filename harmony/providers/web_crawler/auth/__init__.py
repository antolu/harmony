from __future__ import annotations

from harmony._mod_replace import replace_modname

from ._cli import main as cli_main
from ._config import AuthConfig, AuthProviderConfig, OIDCAuthConfig
from ._middleware import AuthMiddleware
from ._registry import AuthProviderRegistry
from ._session import AuthSession

replace_modname(AuthConfig, __name__)
replace_modname(AuthMiddleware, __name__)
replace_modname(AuthProviderRegistry, __name__)
replace_modname(AuthSession, __name__)
replace_modname(OIDCAuthConfig, __name__)
replace_modname(cli_main, __name__)

__all__ = [
    "AuthConfig",
    "AuthMiddleware",
    "AuthProviderConfig",
    "AuthProviderRegistry",
    "AuthSession",
    "OIDCAuthConfig",
    "cli_main",
]
