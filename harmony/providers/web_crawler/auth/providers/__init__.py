from __future__ import annotations

from ._base import AuthProvider
from ._oidc import OIDCAuth

__all__ = ["AuthProvider", "OIDCAuth"]
