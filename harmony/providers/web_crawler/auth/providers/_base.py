from __future__ import annotations

import abc
import asyncio
import re
import typing

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None  # type: ignore[assignment,misc]  # optional dependency: beautifulsoup4

try:
    import litellm
except ImportError:
    litellm = None  # type: ignore[assignment]  # optional dependency: litellm

if typing.TYPE_CHECKING:
    from scrapy import Request
    from scrapy.http import Response

    from .._session import AuthSession

# Multilingual access denied/login required keywords (10 languages)
# Used as fast pre-filter before expensive LLM call
ACCESS_DENIED_KEYWORDS = [
    # English
    "access denied",
    "permission denied",
    "unauthorized",
    "not authorized",
    "login required",
    "sign in required",
    "authentication required",
    # French
    "accès refusé",
    "accès interdit",
    "non autorisé",
    "connexion requise",
    # German
    "zugriff verweigert",
    "nicht autorisiert",
    "anmeldung erforderlich",
    # Spanish
    "acceso denegado",
    "no autorizado",
    "inicio de sesión requerido",
    # Italian
    "accesso negato",
    "non autorizzato",
    "accesso richiesto",
    # Portuguese
    "acesso negado",
    "não autorizado",
    "login necessário",
    # Dutch
    "toegang geweigerd",
    "niet geautoriseerd",
    "inloggen vereist",
    # Russian (transliterated for regex safety)
    "доступ запрещен",
    "не авторизован",
    "требуется вход",
    # Chinese (simplified)
    "访问被拒绝",
    "未经授权",
    "需要登录",
    # Japanese
    "アクセス拒否",
    "認証が必要",
    "ログインが必要",
    # Korean
    "접근 거부",
    "권한 없음",
    "로그인 필요",
    # Arabic
    "تم رفض الوصول",
    "غير مصرح",
]

# Compile pattern for fast matching (case-insensitive)
_ACCESS_DENIED_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in ACCESS_DENIED_KEYWORDS),
    re.IGNORECASE,
)

_HTTP_OK = 200


def _run_llm_check(html: str, model: str, max_length: int) -> bool:
    """Run synchronous LLM check to determine if page is access-denied."""
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.string if soup.title else ""
    h1_tag = soup.find("h1")
    h1 = h1_tag.get_text(strip=True) if h1_tag else ""
    for script in soup(["script", "style"]):
        script.decompose()
    text = soup.get_text(separator=" ", strip=True)[:max_length]
    prompt = (
        f"Web Page Title: {title}\n"
        f"Main Header: {h1}\n"
        f"Content Snippet: {text}\n\n"
        "Task: Determine if the ENTIRE content of this page is replaced by an access denied message "
        "or login prompt. "
        "CRITICAL: Ignore standard login links in headers/menus. "
        "CRITICAL: Ignore technical server warnings (e.g. PHP warnings, Drupal errors) unless "
        "they are accompanied by an explicit 'Access Denied' message that blocks content. "
        "If the page contains valid content (articles, guides, descriptions) below the warnings, "
        "return FALSE.\n"
        "Response: Return ONLY 'TRUE' if access is strictly denied, or 'FALSE' otherwise."
    )
    result = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=10,
        temperature=0,
    )
    answer = result.choices[0].message.content.strip().upper()
    return "TRUE" in answer


class AuthProvider(abc.ABC):
    """Base class for authentication providers."""

    def __init__(
        self,
        domain_patterns: list[str],
        *,
        semantic_auth_detection: bool = False,
        semantic_auth_model: str = "",
        max_semantic_check_length: int = 500,
    ) -> None:
        self._domain_patterns = [re.compile(p) for p in domain_patterns]
        self.semantic_auth_detection = semantic_auth_detection
        self.semantic_auth_model = semantic_auth_model
        self.max_semantic_check_length = max_semantic_check_length

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
    @abc.abstractmethod
    def provider_type(self) -> str:
        """Return the provider type identifier."""

    @abc.abstractmethod
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

    @abc.abstractmethod
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
        Note: Subclasses should call super().is_auth_required(response) if they want
        to fallback to default semantic checks.

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
            header_loc = response.headers.get(b"Location")
            location = (
                header_loc.decode("utf-8", errors="ignore")
                if isinstance(header_loc, bytes)
                else ""
            )
            if any(
                indicator in location.lower()
                for indicator in ["login", "auth", "signin", "sso"]
            ):
                return True

        return False

    async def is_auth_required_async(self, response: Response) -> bool:
        """
        Async version of is_auth_required to support semantic checks.
        Uses fast keyword pre-filter before expensive LLM call.
        """
        if self.is_auth_required(response):
            return True

        if not self.semantic_auth_detection or not self.semantic_auth_model:
            return False

        if response.status != _HTTP_OK:
            return False

        # Fast pre-filter: check for access denied keywords (multilingual)
        # Only call LLM if suspicious keywords are found
        try:
            html = response.text
        except Exception:
            return False

        if not _ACCESS_DENIED_PATTERN.search(html):
            return False

        # Keywords found - run LLM check in thread pool to avoid blocking
        return await self._perform_semantic_check(response, html)

    async def _perform_semantic_check(self, response: Response, html: str) -> bool:
        """Perform LLM-based semantic check on response content.

        Runs in a thread pool to avoid blocking the Twisted reactor.
        """
        if BeautifulSoup is None or litellm is None:
            return False

        def _sync_llm_check() -> bool:
            """Synchronous LLM check to run in thread pool."""
            try:
                return _run_llm_check(
                    html, self.semantic_auth_model, self.max_semantic_check_length
                )
            except Exception:
                return False

        # Run in thread pool to avoid blocking Twisted/Scrapy
        return await asyncio.to_thread(_sync_llm_check)

    def is_interactive(self) -> bool:
        """Return True if this provider requires interactive authentication."""
        return False

    def is_auth_domain(self, url: str) -> bool:
        """
        Check if the given URL belongs to the authentication provider itself.

        This allows the middleware to block requests to the auth provider
        (to prevent crawling login pages or getting stuck in loops).
        """
        return False
