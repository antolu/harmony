from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from harmony.crawler.auth.providers.base import AuthProvider
from harmony.crawler.auth.session import AuthSession

if TYPE_CHECKING:
    from scrapy import Request

    from harmony.crawler.auth.config import StaticCookieAuthConfig


class StaticCookieAuth(AuthProvider):
    """Authentication using static cookies."""

    def __init__(self, config: StaticCookieAuthConfig) -> None:
        super().__init__(config.domains)
        self.config = config
        self._cookies: dict[str, str] = {}
        self._load_cookies()

    def _load_cookies(self) -> None:
        """Load cookies from config or file."""
        if self.config.cookies:
            self._cookies = self.config.cookies.copy()
        elif self.config.cookie_file and self.config.cookie_file.exists():
            # Support various cookie file formats
            content = self.config.cookie_file.read_text()
            # Simple key=value format, one per line
            for line in content.strip().split("\n"):
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    self._cookies[key.strip()] = value.strip()

    @property
    def provider_type(self) -> str:
        return "static_cookie"

    async def authenticate(
        self, subdomain: str, trigger_url: str | None = None
    ) -> AuthSession:
        """Return session with static cookies."""
        return AuthSession(
            provider_type=self.provider_type,
            subdomain=subdomain,
            domain_pattern=self.get_matching_pattern(subdomain) or "",
            created_at=datetime.now(),
            expires_at=None,  # Static cookies don't expire (managed externally)
            cookies=self._cookies.copy(),
        )

    def apply_to_request(self, request: Request, session: AuthSession) -> Request:
        """Apply cookies to request."""
        if session.cookies:
            # Merge with existing cookies
            existing = request.headers.get(b"Cookie", b"").decode(
                "utf-8", errors="ignore"
            )
            new_cookies = "; ".join(f"{k}={v}" for k, v in session.cookies.items())
            cookie_header = f"{existing}; {new_cookies}" if existing else new_cookies
            request.headers[b"Cookie"] = cookie_header.encode()
        return request
