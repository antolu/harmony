from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from harmony.crawler.auth.providers.base import AuthProvider
from harmony.crawler.auth.session import AuthSession

if TYPE_CHECKING:
    from scrapy import Request

    from harmony.crawler.auth.config import BearerTokenAuthConfig


class BearerTokenAuth(AuthProvider):
    """Bearer token authentication provider."""

    def __init__(self, config: BearerTokenAuthConfig) -> None:
        super().__init__(
            config.domains,
            semantic_auth_detection=config.semantic_auth_detection,
            semantic_auth_model=config.semantic_auth_model,
            max_semantic_check_length=config.max_semantic_check_length,
        )
        self.config = config

    @property
    def provider_type(self) -> str:
        return "bearer"

    async def authenticate(
        self, subdomain: str, trigger_url: str | None = None
    ) -> AuthSession:
        """Return session with Bearer token header."""
        header_value = f"{self.config.header_prefix} {self.config.token}"
        return AuthSession(
            provider_type=self.provider_type,
            subdomain=subdomain,
            domain_pattern=self.get_matching_pattern(subdomain) or "",
            created_at=datetime.now(),
            expires_at=None,
            headers={self.config.header_name: header_value},
        )

    def apply_to_request(self, request: Request, session: AuthSession) -> Request:
        """Apply Bearer token header to request."""
        for header_name, header_value in session.headers.items():
            request.headers[header_name.encode()] = header_value.encode()
        return request
