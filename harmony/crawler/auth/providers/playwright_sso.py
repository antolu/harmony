from __future__ import annotations

import asyncio
import contextlib
import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from harmony.crawler.auth.providers.base import AuthProvider
from harmony.crawler.auth.session import AuthSession
from harmony.crawler.logger import logger

try:
    from playwright.async_api import Page, async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None  # type: ignore[assignment,misc]
    Page = None  # type: ignore[assignment,misc]

if TYPE_CHECKING:
    from scrapy import Request
    from scrapy.http import Response

    from harmony.crawler.auth.config import PlaywrightSSOAuthConfig


class AuthenticationCancelledError(Exception):
    """Raised when user cancels authentication."""


class PlaywrightSSOAuth(AuthProvider):
    """Interactive SSO authentication via Playwright browser."""

    def __init__(self, config: PlaywrightSSOAuthConfig) -> None:
        super().__init__(config.domains)
        self.config = config
        self._storage_state: dict | None = None
        self._load_storage_state()

    def _load_storage_state(self) -> None:
        """Load saved storage state from file if exists."""
        if self.config.storage_state_file and self.config.storage_state_file.exists():
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
        if not self.config.storage_state_file:
            return
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
        all_cookies = self._storage_state.get("cookies", [])
        logger.debug(
            f"Extracting cookies for {subdomain} from {len(all_cookies)} total cookies"
        )

        normalized_subdomain = subdomain.lstrip(".")

        for cookie in all_cookies:
            cookie_domain = cookie.get("domain", "")
            normalized_cookie_domain = cookie_domain.lstrip(".")

            is_match = (
                normalized_subdomain == normalized_cookie_domain
                or normalized_subdomain.endswith(f".{normalized_cookie_domain}")
            )

            if is_match:
                cookies[cookie["name"]] = cookie["value"]
                logger.debug(f"  [MATCH] {cookie['name']} ({cookie_domain})")
            else:
                logger.debug(f"  [SKIP ] {cookie['name']} ({cookie_domain})")

        logger.info(f"Selected {len(cookies)} cookies for {subdomain}")
        return cookies

    @property
    def provider_type(self) -> str:
        return "playwright_sso"

    def is_interactive(self) -> bool:
        return True

    async def _check_element_exists(self, page: Page, selector: str) -> bool:
        """Check if an element matching the selector exists on the page."""
        try:
            locator = page.locator(selector)
            count = await locator.count()
        except Exception:
            return False
        else:
            return count > 0

    async def _detect_auth_state(self, page: Page) -> tuple[bool | None, str | None]:
        """
        Detect authentication state by checking for login/logout indicators.

        Returns:
            (is_authenticated, matched_selector)
            - (True, selector) if authenticated marker found
            - (False, selector) if login required marker found
            - (None, None) if state cannot be determined
        """
        for selector in self.config.authenticated_markers:
            if await self._check_element_exists(page, selector):
                logger.debug(f"Found authenticated marker: {selector}")
                return True, selector

        for selector in self.config.login_required_markers:
            if await self._check_element_exists(page, selector):
                logger.debug(f"Found login-required marker: {selector}")
                return False, selector

        return None, None

    async def _wait_for_authentication(
        self, page: Page, target_netloc: str, start_time: float
    ) -> None:
        """
        Wait for authentication to complete using element-based detection.

        Exits when:
        1. Authenticated marker appears (user logged in)
        2. User closes browser (manual override)
        3. Timeout exceeded
        4. Cancellation requested (Ctrl+C)
        """
        check_interval_ms = 500
        timeout_ms = self.config.timeout_seconds * 1000

        while True:
            elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
            if elapsed >= timeout_ms:
                logger.warning(
                    f"Authentication timeout after {self.config.timeout_seconds}s"
                )
                break

            try:
                is_authenticated, marker = await self._detect_auth_state(page)
            except asyncio.CancelledError:
                logger.warning("Authentication cancelled by user")
                raise

            if is_authenticated is True:
                logger.info(f"Authentication confirmed via: {marker}")
                await self._wait_for_page_stable(page)
                return

            if is_authenticated is False:
                current_url = page.url
                current_netloc = urlparse(current_url).netloc

                if current_netloc != target_netloc:
                    logger.info(
                        f"On auth provider ({current_netloc}), waiting for redirect..."
                    )
                else:
                    logger.debug("Login form detected, waiting for user interaction...")

            await page.wait_for_timeout(check_interval_ms)

    async def _wait_for_page_stable(self, page: Page, timeout_ms: int = 5000) -> None:
        """Wait for page to become stable (DOM loaded, no major pending requests)."""
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)

    async def authenticate(  # noqa: PLR0912, PLR0915, PLR0914
        self, subdomain: str, trigger_url: str | None = None
    ) -> AuthSession:
        """Perform interactive SSO login via Playwright browser."""
        if not PLAYWRIGHT_AVAILABLE or async_playwright is None:
            msg = "Playwright is required for SSO authentication. Install with: pip install playwright && playwright install"
            raise ImportError(msg)

        logger.info(f"Starting interactive SSO login for {self.config.name}")
        if self.config.login_url:
            logger.info(f"Login URL: {self.config.login_url}")

        if not self.config.headless:
            logger.info(
                "A browser window will open. Please complete the login if required."
            )
            logger.info(f"Timeout: {self.config.timeout_seconds} seconds")
            logger.info("The window will close automatically when login is detected.")

        async with async_playwright() as p:
            browser_launcher = getattr(p, self.config.browser_type)
            launch_kwargs: dict[str, Any] = {"headless": self.config.headless}
            if self.config.proxy:
                launch_kwargs["proxy"] = self.config.proxy

            browser = await browser_launcher.launch(**launch_kwargs)

            context_kwargs: dict[str, Any] = {"user_agent": self.config.user_agent}
            if self._storage_state:
                context_kwargs["storage_state"] = self._storage_state

            context = await browser.new_context(**context_kwargs)
            page = await context.new_page()

            user_cancelled = False

            try:
                start_url = trigger_url or self.config.login_url
                if not start_url:
                    msg = "No login_url configured and no trigger_url available"
                    raise ValueError(msg)  # noqa: TRY301

                target_netloc = (
                    urlparse(trigger_url).netloc if trigger_url else subdomain
                )

                logger.info(f"Navigating to {start_url}")
                await page.goto(start_url, wait_until="domcontentloaded")

                if self.config.success_url_pattern:
                    logger.info(
                        f"Waiting for URL matching: {self.config.success_url_pattern}"
                    )
                    await page.wait_for_url(
                        re.compile(self.config.success_url_pattern),
                        timeout=self.config.timeout_seconds * 1000,
                    )

                elif self.config.login_complete_marker:
                    logger.info(
                        f"Waiting for element: {self.config.login_complete_marker}"
                    )
                    await page.wait_for_selector(
                        self.config.login_complete_marker,
                        timeout=self.config.timeout_seconds * 1000,
                    )

                else:
                    await self._wait_for_page_stable(page)

                    is_authenticated, marker = await self._detect_auth_state(page)

                    if is_authenticated is True:
                        logger.info(
                            f"Already authenticated (found: {marker}). No login required."
                        )

                    elif is_authenticated is False:
                        logger.info(
                            f"Login required (found: {marker}). Waiting for user to authenticate..."
                        )
                        start_time = asyncio.get_event_loop().time()
                        await self._wait_for_authentication(
                            page, target_netloc, start_time
                        )

                    else:
                        logger.info(
                            "Could not determine auth state. Waiting for user interaction..."
                        )
                        logger.info(
                            "Tip: Configure 'authenticated_markers' or 'login_required_markers' for faster detection."
                        )
                        start_time = asyncio.get_event_loop().time()
                        await self._wait_for_authentication(
                            page, target_netloc, start_time
                        )

                logger.info("Login completed successfully!")

            except Exception as e:
                error_str = str(e)
                if "Target closed" in error_str or "Page closed" in error_str:
                    final_state, _ = await self._safe_detect_auth_state(page)
                    if final_state is True:
                        logger.info("Browser closed after successful authentication.")
                    else:
                        logger.warning(
                            "Browser closed by user. Could not confirm authentication."
                        )
                        user_cancelled = True
                elif "Timeout" in error_str:
                    logger.warning(f"Authentication timed out: {e}")
                else:
                    logger.warning(f"Browser interaction interrupted: {e}")

            try:
                storage_state = await context.storage_state()
                self._save_storage_state(storage_state)
            except Exception as e:
                logger.warning(f"Could not save storage state: {e}")

            await browser.close()

        if user_cancelled:
            logger.warning(
                "Authentication may be incomplete. Cookies saved but might not be valid."
            )

        cookies = self._extract_cookies_for_subdomain(subdomain)

        return AuthSession(
            provider_type=self.provider_type,
            subdomain=subdomain,
            domain_pattern=self.get_matching_pattern(subdomain) or "",
            created_at=datetime.now(),
            expires_at=None,
            cookies=cookies,
            storage_state_file=self.config.storage_state_file,
        )

    async def _safe_detect_auth_state(
        self, page: Page
    ) -> tuple[bool | None, str | None]:
        """Detect auth state, returning (None, None) if page is closed."""
        try:
            return await self._detect_auth_state(page)
        except Exception:
            return None, None

    async def refresh_session_for_subdomain(self, subdomain: str) -> AuthSession | None:
        """Try to get session for a new subdomain using existing storage state."""
        if not self._storage_state:
            return None

        cookies = self._extract_cookies_for_subdomain(subdomain)
        if not cookies:
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
            if hasattr(request, "cookies"):
                if not request.cookies:
                    request.cookies = {}
                if isinstance(request.cookies, dict):
                    request.cookies.update(session.cookies)

            request.cookies = session.cookies

            cookie_header = "; ".join([f"{k}={v}" for k, v in session.cookies.items()])
            request.headers["Cookie"] = cookie_header
            request.headers["User-Agent"] = self.config.user_agent

        return request

    def is_auth_required(self, response: Response) -> bool:
        """Check if response indicates SSO authentication is required."""
        if response.status in {401, 403}:
            return True

        if response.status == 404:  # noqa: PLR2004
            return False

        current_url = response.url.lower()

        if current_url.endswith("robots.txt"):
            return False

        for pattern in self.config.auth_domain_patterns:
            if pattern.lower() in current_url:
                logger.info(f"Landed on auth URL (matched '{pattern}'): {current_url}")
                return True

        if response.status in {301, 302, 303, 307, 308}:
            loc_header = response.headers.get(b"Location", b"")
            location = ""
            if loc_header:
                try:
                    location = loc_header.decode("utf-8", errors="ignore").lower()
                except Exception:
                    location = str(loc_header).lower()

            for pattern in self.config.auth_domain_patterns:
                if pattern.lower() in location:
                    logger.info(
                        f"Auth redirect detected (matched '{pattern}'): {location}"
                    )
                    return True

        return False

    def has_valid_storage_state(self) -> bool:
        """Check if we have saved storage state."""
        return self._storage_state is not None and bool(
            self._storage_state.get("cookies")
        )

    def is_auth_domain(self, url: str) -> bool:
        """Check if URL belongs to the auth provider."""
        if self.config.login_url:
            login_netloc = urlparse(self.config.login_url).netloc
            if login_netloc and login_netloc in url:
                return True

        url_lower = url.lower()
        for pattern in self.config.auth_domain_patterns:
            if pattern.lower() in url_lower:
                return True

        return False
