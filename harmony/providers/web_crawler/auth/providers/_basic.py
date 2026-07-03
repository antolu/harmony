from __future__ import annotations

import base64
import typing
from datetime import datetime

from .._session import AuthSession
from ._base import AuthProvider

if typing.TYPE_CHECKING:
    from scrapy import Request

    from .._config import BasicAuthConfig


class BasicAuth(AuthProvider):
    """HTTP Basic Authentication provider."""

    def __init__(self, config: BasicAuthConfig) -> None:
        super().__init__(
            config.domains,
            semantic_auth_detection=config.semantic_auth_detection,
            semantic_auth_model=config.semantic_auth_model,
            max_semantic_check_length=config.max_semantic_check_length,
        )
        self.config = config
        self._auth_header = self._build_auth_header()

    def _build_auth_header(self) -> str:
        """Build the Authorization header value."""
        credentials = f"{self.config.username}:{self.config.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    @property
    def provider_type(self) -> str:
        return "basic"

    async def authenticate(
        self, subdomain: str, trigger_url: str | None = None
    ) -> AuthSession:
        """Return session with Basic Auth header."""
        return AuthSession(
            provider_type=self.provider_type,
            subdomain=subdomain,
            domain_pattern=self.get_matching_pattern(subdomain) or "",
            created_at=datetime.now(),
            expires_at=None,
            headers={"Authorization": self._auth_header},
        )

    def apply_to_request(self, request: Request, session: AuthSession) -> Request:
        """Apply Authorization header to request."""
        for header_name, header_value in session.headers.items():
            request.headers[header_name.encode()] = header_value.encode()
        return request
