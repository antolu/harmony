from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import TYPE_CHECKING

from harmony.crawler.auth.providers.base import AuthProvider
from harmony.crawler.auth.session import AuthSession
from harmony.crawler.logger import logger

if TYPE_CHECKING:
    from scrapy import Request
    from scrapy.http import Response

    from harmony.crawler.auth.config import PlaywrightSSOAuthConfig


class PlaywrightSSOAuth(AuthProvider):
    """Interactive SSO authentication via Playwright browser."""

    def __init__(self, config: PlaywrightSSOAuthConfig) -> None:
        super().__init__(config.domains)
        self.config = config
        self._storage_state: dict | None = None
        self._load_storage_state()

    def _load_storage_state(self) -> None:
        """Load saved storage state from file if exists."""
        if self.config.storage_state_file.exists():
            try:
                with open(self.config.storage_state_file, encoding="utf-8") as f:
                    self._storage_state = json.load(f)
                logger.info(
                    f"Loaded existing SSO state from {self.config.storage_state_file}"
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load SSO state: {e}")
                self._storage_state = None

    def _save_storage_state(self, state: dict) -> None:
        """Save storage state to file."""
        self.config.storage_state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config.storage_state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        self._storage_state = state
        logger.info(f"Saved SSO state to {self.config.storage_state_file}")

    def _extract_cookies_for_subdomain(self, subdomain: str) -> dict[str, str]:
        """Extract cookies relevant to a subdomain from storage state."""
        if not self._storage_state:
            return {}

        cookies = {}
        for cookie in self._storage_state.get("cookies", []):
            cookie_domain = cookie.get("domain", "")
            # Match if cookie domain matches subdomain (with or without leading dot)
            if subdomain == cookie_domain or subdomain.endswith((
                cookie_domain,
                cookie_domain.lstrip("."),
            )):
                cookies[cookie["name"]] = cookie["value"]

        return cookies

    @property
    def provider_type(self) -> str:
        return "playwright_sso"

    def is_interactive(self) -> bool:
        return True

    async def authenticate(
        self, subdomain: str, trigger_url: str | None = None
    ) -> AuthSession:
        """Perform interactive SSO login via Playwright browser."""
        # Import playwright only when needed (optional dependency)
        try:
            from playwright.async_api import async_playwright  # noqa: PLC0415
        except ImportError as e:
            msg = "Playwright is required for SSO authentication. Install with: pip install playwright && playwright install"
            raise ImportError(msg) from e

        logger.info(f"Starting interactive SSO login for {self.config.name}")
        logger.info(f"Login URL: {self.config.login_url}")

        if not self.config.headless:
            logger.info(
                "A browser window will open. Please complete the login (including 2FA if required)."
            )
            logger.info(f"Timeout: {self.config.timeout_seconds} seconds")

        async with async_playwright() as p:
            # Launch browser
            browser_launcher = getattr(p, self.config.browser_type)
            browser = await browser_launcher.launch(headless=self.config.headless)

            # Create context - optionally with existing state for session refresh
            context_kwargs = {}
            if self._storage_state:
                context_kwargs["storage_state"] = self._storage_state

            context = await browser.new_context(**context_kwargs)
            page = await context.new_page()

            try:
                # Navigate to login URL (or trigger URL if provided)
                start_url = trigger_url or self.config.login_url
                await page.goto(start_url)

                # Wait for login to complete
                if self.config.success_url_pattern:
                    # Wait for URL to match success pattern
                    logger.info(
                        f"Waiting for URL matching: {self.config.success_url_pattern}"
                    )
                    await page.wait_for_url(
                        re.compile(self.config.success_url_pattern),
                        timeout=self.config.timeout_seconds * 1000,
                    )
                elif self.config.login_complete_marker:
                    # Wait for specific element/text
                    logger.info(f"Waiting for: {self.config.login_complete_marker}")
                    await page.wait_for_selector(
                        self.config.login_complete_marker,
                        timeout=self.config.timeout_seconds * 1000,
                    )
                else:
                    # Wait for navigation away from login page
                    logger.info("Waiting for login to complete...")
                    await page.wait_for_load_state("networkidle")
                    # Give time for cookies to settle
                    await asyncio.sleep(2)

                logger.info("Login completed successfully!")

                # Save storage state
                storage_state = await context.storage_state()
                self._save_storage_state(storage_state)

            finally:
                await browser.close()

        # Extract cookies for this specific subdomain
        cookies = self._extract_cookies_for_subdomain(subdomain)

        return AuthSession(
            provider_type=self.provider_type,
            subdomain=subdomain,
            domain_pattern=self.get_matching_pattern(subdomain) or "",
            created_at=datetime.now(),
            expires_at=None,  # SSO sessions typically long-lived, we'll detect expiry via 403
            cookies=cookies,
            storage_state_file=self.config.storage_state_file,
        )

    async def refresh_session_for_subdomain(self, subdomain: str) -> AuthSession | None:
        """
        Try to get session for a new subdomain using existing storage state.

        This is called when we hit a new subdomain under the same SSO umbrella.
        The SSO cookies should allow automatic authentication.
        """
        if not self._storage_state:
            return None

        cookies = self._extract_cookies_for_subdomain(subdomain)
        if not cookies:
            # No cookies for this subdomain - may need full re-auth
            return None

        return AuthSession(
            provider_type=self.provider_type,
            subdomain=subdomain,
            domain_pattern=self.get_matching_pattern(subdomain) or "",
            created_at=datetime.now(),
            expires_at=None,
            cookies=cookies,
            storage_state_file=self.config.storage_state_file,
        )

    def apply_to_request(self, request: Request, session: AuthSession) -> Request:
        """Apply SSO cookies to request."""
        if session.cookies:
            existing = request.headers.get(b"Cookie", b"").decode(
                "utf-8", errors="ignore"
            )
            new_cookies = "; ".join(f"{k}={v}" for k, v in session.cookies.items())
            cookie_header = f"{existing}; {new_cookies}" if existing else new_cookies
            request.headers[b"Cookie"] = cookie_header.encode()
        return request

    def is_auth_required(self, response: Response) -> bool:
        """Check if response indicates SSO authentication is required."""
        # Standard checks
        if response.status in {401, 403}:
            return True

        # Check for SSO redirect
        if response.status in {302, 303, 307}:
            location = response.headers.get(b"Location", b"").decode(
                "utf-8", errors="ignore"
            )
            # CERN SSO patterns
            if any(
                indicator in location.lower()
                for indicator in [
                    "auth.cern.ch",
                    "login.cern.ch",
                    "keycloak",
                    "/auth/realms/",
                    "signin",
                    "sso",
                ]
            ):
                return True

        # Check response body for login indicators (if HTML)
        if hasattr(response, "text"):
            body_lower = response.text[:2000].lower()  # Check first 2KB
            if any(
                indicator in body_lower
                for indicator in [
                    "sign in with your cern account",
                    "cern single sign-on",
                    "authentication required",
                    "please log in",
                    "access denied",
                ]
            ):
                return True

        return False

    def has_valid_storage_state(self) -> bool:
        """Check if we have saved storage state."""
        return self._storage_state is not None and bool(
            self._storage_state.get("cookies")
        )
