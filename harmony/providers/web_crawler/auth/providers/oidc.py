from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import httpx

from harmony.core import logger
from harmony.providers.web_crawler.auth.providers.base import AuthProvider
from harmony.providers.web_crawler.auth.session import AuthSession

if TYPE_CHECKING:
    from scrapy import Request
    from scrapy.http import Response

    from harmony.providers.web_crawler.auth.config import OIDCAuthConfig


def build_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) using S256."""
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


class OIDCAuth(AuthProvider):
    """OIDC auth provider supporting client_credentials and authorization_code flows."""

    def __init__(self, config: OIDCAuthConfig) -> None:
        super().__init__(
            config.domains,
            semantic_auth_detection=config.semantic_auth_detection,
            semantic_auth_model=config.semantic_auth_model,
            max_semantic_check_length=config.max_semantic_check_length,
        )
        self.config = config
        self._token_endpoint: str | None = None
        self._auth_endpoint: str | None = None
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._refresh_lock = asyncio.Lock()
        self.pending_states: dict[str, str] = {}
        self._load_state()

    def _load_state(self) -> None:
        if not self.config.storage_state_file:
            return
        p = Path(self.config.storage_state_file)
        if not p.exists():
            return
        try:
            self._load_state_from_file(p)
        except Exception as e:
            logger.warning(f"Failed to load OIDC state: {e}")

    def _load_state_from_file(self, p: Path) -> None:
        data = json.loads(p.read_text(encoding="utf-8"))
        self._access_token = data.get("access_token")
        self._refresh_token = data.get("refresh_token")
        expires_at = data.get("expires_at")
        if expires_at:
            self._token_expires_at = datetime.fromisoformat(expires_at)

    def _save_state(self) -> None:
        if not self.config.storage_state_file:
            return
        p = Path(self.config.storage_state_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "expires_at": self._token_expires_at.isoformat()
            if self._token_expires_at
            else None,
        }
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def _discover(self) -> None:
        url = f"{self.config.issuer_url.rstrip('/')}/.well-known/openid-configuration"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10)
            resp.raise_for_status()
            doc = resp.json()
        self._token_endpoint = doc["token_endpoint"]
        self._auth_endpoint = doc.get("authorization_endpoint")
        logger.info(f"OIDC discovery complete for {self.config.name}")

    async def ensure_discovered(self) -> None:
        if not self._token_endpoint:
            await self._discover()

    def _token_needs_refresh(self) -> bool:
        if not self._access_token:
            return True
        if not self._token_expires_at:
            return False
        buffer = timedelta(seconds=self.config.token_expiry_buffer_seconds)
        return datetime.now(UTC) + buffer >= self._token_expires_at

    async def _fetch_token(self, data: dict) -> None:
        assert self._token_endpoint
        if self.config.audience:
            data["audience"] = self.config.audience
        async with httpx.AsyncClient() as client:
            resp = await client.post(self._token_endpoint, data=data, timeout=15)
            resp.raise_for_status()
            payload = resp.json()
        self._access_token = payload["access_token"]
        self._refresh_token = payload.get("refresh_token")
        expires_in = int(payload.get("expires_in", 300))
        self._token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
        self._save_state()
        logger.info(
            f"OIDC token acquired for {self.config.name}, expires in {expires_in}s"
        )

    async def do_client_credentials(self) -> None:
        data: dict = {
            "grant_type": "client_credentials",
            "client_id": self.config.client_id,
            "scope": " ".join(self.config.scopes),
        }
        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret
        await self._fetch_token(data)

    async def _do_refresh(self) -> None:
        if not self._refresh_token:
            if self.config.flow == "client_credentials":
                await self.do_client_credentials()
                return
            msg = f"No refresh token available for {self.config.name}"
            raise RuntimeError(msg)
        data: dict = {
            "grant_type": "refresh_token",
            "client_id": self.config.client_id,
            "refresh_token": self._refresh_token,
        }
        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret
        try:
            await self._fetch_token(data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in {400, 401}:
                logger.warning(
                    f"Refresh token expired for {self.config.name}, re-authenticating"
                )
                self._refresh_token = None
                if self.config.flow == "client_credentials":
                    await self.do_client_credentials()
                else:
                    self._access_token = None
                    msg = f"Session expired for {self.config.name}, re-login required"
                    raise RuntimeError(msg) from e
            else:
                raise

    async def ensure_valid(self) -> None:
        """Ensure the access token is valid, refreshing if needed. Called by middleware."""
        if not self._token_needs_refresh():
            return
        async with self._refresh_lock:
            if not self._token_needs_refresh():
                return
            await self.ensure_discovered()
            await self._do_refresh()

    @property
    def provider_type(self) -> str:
        return "oidc"

    def is_interactive(self) -> bool:
        return self.config.flow == "authorization_code"

    async def authenticate(
        self, subdomain: str, trigger_url: str | None = None
    ) -> AuthSession:
        await self.ensure_discovered()
        if self.config.flow == "client_credentials":
            await self.do_client_credentials()
        return self.make_session(subdomain)

    def make_session(self, subdomain: str) -> AuthSession:
        return AuthSession(
            provider_type=self.provider_type,
            subdomain=subdomain,
            domain_pattern=self.get_matching_pattern(subdomain) or "",
            created_at=datetime.now(UTC),
            expires_at=self._token_expires_at,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )

    def apply_to_request(self, request: Request, session: AuthSession) -> Request:
        request.headers["Authorization"] = f"Bearer {self._access_token}"
        return request

    def build_auth_url(self, redirect_uri: str) -> tuple[str, str, str]:
        """Build authorization URL for authorization_code flow. Returns (url, state, code_verifier)."""
        assert self._auth_endpoint, "Discovery not complete"
        state = secrets.token_urlsafe(16)
        verifier, challenge = build_pkce_pair()
        self.pending_states[state] = verifier

        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(self.config.scopes),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        url = f"{self._auth_endpoint}?{urlencode(params)}"
        return url, state, verifier

    async def receive_code(self, code: str, state: str, redirect_uri: str) -> None:
        """Exchange authorization code for tokens after callback."""
        verifier = self.pending_states.pop(state, None)
        if verifier is None:
            msg = "Invalid or unknown state parameter"
            raise ValueError(msg)
        await self.ensure_discovered()
        data: dict = {
            "grant_type": "authorization_code",
            "client_id": self.config.client_id,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        }
        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret
        await self._fetch_token(data)

    def is_auth_required(self, response: Response) -> bool:
        if response.status in {401, 403}:
            return True
        if response.status in {302, 303, 307}:
            location = (
                response.headers
                .get(b"Location", b"")
                .decode("utf-8", errors="ignore")
                .lower()
            )
            if any(kw in location for kw in ["login", "auth", "signin", "sso"]):
                return True
        return False
