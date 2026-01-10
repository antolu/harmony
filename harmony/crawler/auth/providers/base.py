from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scrapy import Request
    from scrapy.http import Response

    from harmony.crawler.auth.session import AuthSession


class AuthProvider(ABC):
    """Base class for authentication providers."""

    def __init__(self, domain_patterns: list[str]) -> None:
        self._domain_patterns = [re.compile(p) for p in domain_patterns]

    @property
    def domain_patterns(self) -> list[re.Pattern[str]]:
        """Get the compiled domain patterns."""
        return self._domain_patterns

    def matches_domain(self, subdomain: str) -> bool:
        """Check if this provider handles the given subdomain."""
        return any(p.match(subdomain) for p in self._domain_patterns)

    def get_matching_pattern(self, subdomain: str) -> str | None:
        """Get the pattern that matches this subdomain."""
        for p in self._domain_patterns:
            if p.match(subdomain):
                return p.pattern
        return None

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Return the provider type identifier."""

    @abstractmethod
    async def authenticate(
        self, subdomain: str, trigger_url: str | None = None
    ) -> AuthSession:
        """
        Perform authentication and return session.

        Args:
            subdomain: The subdomain requiring authentication
            trigger_url: The URL that triggered authentication (for context)

        Returns:
            AuthSession with credentials to apply to requests
        """

    @abstractmethod
    def apply_to_request(self, request: Request, session: AuthSession) -> Request:
        """
        Apply authentication credentials to a request.

        Args:
            request: Scrapy request to modify
            session: Session containing credentials

        Returns:
            Modified request with auth credentials
        """

    def is_auth_required(self, response: Response) -> bool:
        """
        Check if response indicates authentication is required.

        Override in subclasses for provider-specific detection.

        Args:
            response: Scrapy response to check

        Returns:
            True if authentication is needed
        """
        # Default: check common auth-required indicators
        if response.status in {401, 403}:
            return True

        # Check for login redirects
        if response.status in {302, 303, 307}:
            location = response.headers.get(b"Location", b"").decode(
                "utf-8", errors="ignore"
            )
            if any(
                indicator in location.lower()
                for indicator in ["login", "auth", "signin", "sso"]
            ):
                return True

        return False

    def is_interactive(self) -> bool:
        """Return True if this provider requires interactive authentication."""
        return False
