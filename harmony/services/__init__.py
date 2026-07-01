from __future__ import annotations

from harmony._mod_replace import replace_modname
from harmony.services._secret_service import SecretValueService

replace_modname(SecretValueService, __name__)

__all__ = [
    "SecretValueService",
]
