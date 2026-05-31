from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlencode

from harmony.api.auth._oidc_core import (
    build_pkce_pair,
    discover_oidc_endpoints,
    fetch_token,
)


@dataclass
class UserOIDCConfig:
    issuer_url: str
    client_id: str
    client_secret: str
    scopes: list[str] = field(default_factory=list)
    internal_url: str = ""


class UserOIDCClient:
    def __init__(self, config: UserOIDCConfig) -> None:
        self.config = config
        self._token_endpoint: str | None = None
        self._auth_endpoint: str | None = None

    async def ensure_discovered(self) -> None:
        if not self._token_endpoint:
            self._token_endpoint, self._auth_endpoint = await discover_oidc_endpoints(
                self.config.issuer_url,
                internal_url=self.config.internal_url,
            )

    def build_auth_url(self, redirect_uri: str, state: str) -> tuple[str, str]:
        verifier, challenge = build_pkce_pair()
        return self.build_auth_url_with_challenge(
            redirect_uri, state, challenge
        ), verifier

    def build_auth_url_with_challenge(
        self, redirect_uri: str, state: str, code_challenge: str
    ) -> str:
        params = {
            "client_id": self.config.client_id,
            "response_type": "code",
            "scope": " ".join(self.config.scopes),
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self._auth_endpoint}?{urlencode(params)}"

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str
    ) -> dict:
        data = {
            "grant_type": "authorization_code",
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
        # Token exchange is server-to-server — use internal URL if available.
        endpoint = self._token_endpoint or ""
        if self.config.internal_url and self.config.issuer_url:
            endpoint = endpoint.replace(
                self.config.issuer_url.rstrip("/"),
                self.config.internal_url.rstrip("/"),
                1,
            )
        return await fetch_token(endpoint, data)
