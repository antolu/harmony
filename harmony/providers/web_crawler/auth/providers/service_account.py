from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import httpx

from harmony.providers.web_crawler.auth.providers.base import AuthProvider
from harmony.providers.web_crawler.auth.session import AuthSession

if TYPE_CHECKING:
    from scrapy import Request

    from harmony.providers.web_crawler.auth.config import ServiceAccountAuthConfig


class ServiceAccountAuth(AuthProvider):
    """OAuth2 client credentials (service account) provider."""

    def __init__(self, config: ServiceAccountAuthConfig) -> None:
        super().__init__(
            config.domains,
            semantic_auth_detection=config.semantic_auth_detection,
            semantic_auth_model=config.semantic_auth_model,
            max_semantic_check_length=config.max_semantic_check_length,
        )
        self.config = config

    @property
    def provider_type(self) -> str:
        return "service_account"

    async def authenticate(
        self, subdomain: str, trigger_url: str | None = None
    ) -> AuthSession:
        """Obtain access token using client credentials flow."""
        async with httpx.AsyncClient() as client:
            data = {
                "grant_type": "client_credentials",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
            }
            if self.config.scope:
                data["scope"] = self.config.scope

            response = await client.post(self.config.token_url, data=data)
            response.raise_for_status()
            token_data = response.json()

        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)

        expires_at = datetime.now() + timedelta(
            seconds=expires_in - self.config.token_expiry_buffer_seconds
        )

        return AuthSession(
            provider_type=self.provider_type,
            subdomain=subdomain,
            domain_pattern=self.get_matching_pattern(subdomain) or "",
            created_at=datetime.now(),
            expires_at=expires_at,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    def apply_to_request(self, request: Request, session: AuthSession) -> Request:
        """Apply access token header to request."""
        for header_name, header_value in session.headers.items():
            request.headers[header_name.encode()] = header_value.encode()
        return request
