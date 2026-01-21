from __future__ import annotations

import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

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

        for cookie in all_cookies:
            cookie_domain = cookie.get("domain", "")
            # Match if cookie domain matches subdomain (with or without leading dot)
            # Standard browser matching:
            # 1. Exact match
            # 2. Domain match (cookie domain is suffix of target domain)

            # Clean domains for comparison
            # cookie_domain often starts with dot (e.g., .google.com)
            # subdomain usually doesn't (e.g., mail.google.com)

            normalized_cookie_domain = cookie_domain.lstrip(".")
            normalized_subdomain = subdomain.lstrip(".")

            # Logic:
            # If cookie is .example.com, it applies to example.com and foo.example.com
            # So: subdomain must END WITH cookie_domain (normalized)

            is_match = False
            if (
                normalized_subdomain == normalized_cookie_domain
                or normalized_subdomain.endswith(f".{normalized_cookie_domain}")
            ):
                is_match = True

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

    async def authenticate(  # noqa: PLR0912, PLR0915, PLR0914
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
            logger.info(
                "IMPORTANT: fail-safe is to WAIT for the page to redirect back to the content before closing!"
            )
            logger.info(f"Timeout: {self.config.timeout_seconds} seconds")

        async with async_playwright() as p:
            # Launch browser
            browser_launcher = getattr(p, self.config.browser_type)
            launch_kwargs: dict[str, Any] = {"headless": self.config.headless}
            if self.config.proxy:
                launch_kwargs["proxy"] = self.config.proxy

            browser = await browser_launcher.launch(**launch_kwargs)

            # Create context - optionally with existing state for session refresh
            context_kwargs: dict[str, Any] = {}
            if self._storage_state:
                context_kwargs["storage_state"] = self._storage_state

            context_kwargs["user_agent"] = self.config.user_agent

            context = await browser.new_context(**context_kwargs)
            page = await context.new_page()

            try:
                # Navigate to login URL. Prefer trigger_url if available (as it initiates correct SSO flow),
                # otherwise fall back to configured login_url.
                start_url = trigger_url or self.config.login_url
                if not start_url:
                    msg = "No login_url configured and no trigger_url available"
                    raise ValueError(msg)

                # IMPORTANT: Use 'commit' only if we want to wait for initial load.
                response = await page.goto(start_url)

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
                    # Smart detection of SSO flow completion
                    current_netloc = urlparse(page.url).netloc
                    target_netloc = (
                        urlparse(trigger_url).netloc if trigger_url else subdomain
                    )

                    if target_netloc:
                        # Listener for auth activity (Event-driven detection for instant bounces)
                        auth_activity = {"detected": False}

                        def on_request(req: Any) -> None:
                            """Flag if request is made to auth provider."""
                            try:
                                u = req.url.lower()
                                # Check for common auth keywords or CERN specific domains
                                if any(
                                    x in u
                                    for x in [
                                        "auth.cern.ch",
                                        "login",
                                        "sso",
                                        "keycloak",
                                        "signin",
                                        "oauth",
                                    ]
                                ):
                                    # Ensure it's not a self-referential asset on the target domain
                                    # (Only flag if leaving the target domain or specifically hitting auth.cern.ch)
                                    req_netloc = urlparse(req.url).netloc
                                    if (
                                        req_netloc != target_netloc
                                        or "auth.cern.ch" in u
                                    ):
                                        auth_activity["detected"] = True
                            except Exception:
                                pass

                        page.on("request", on_request)

                        try:
                            if current_netloc == target_netloc:
                                # Check if we are already authenticated (200 OK)
                                # Only if response exists
                                if response and (response.status in {200, 302}):
                                    logger.info(
                                        "Page loaded explicitly (200 OK). Assuming already authenticated."
                                    )
                                    await page.wait_for_load_state("networkidle")
                                else:
                                    # We are on target but likely 403/Login page. Wait for user to interact.
                                    logger.info(
                                        f"Currently at {current_netloc}. Waiting for login interaction..."
                                    )
                                    logger.info(
                                        "(Close browser or click 'Sign In' to proceed)"
                                    )

                                    # Polling loop to detect Departure OR Instant Bounce
                                    max_checks = (
                                        self.config.timeout_seconds * 2
                                    )  # 0.5s interval
                                    checks = 0

                                    while checks < max_checks:
                                        curr = urlparse(page.url).netloc

                                        # Case 1: Departed (Navigated away)
                                        if curr != target_netloc:
                                            logger.info("Navigated to auth provider.")
                                            # Strictly wait for return
                                            await page.wait_for_url(
                                                lambda u: (
                                                    urlparse(u).netloc == target_netloc
                                                ),
                                                timeout=self.config.timeout_seconds
                                                * 1000,
                                            )
                                            break

                                        # Case 2: Instant Bounce (Trip detected + At Target)
                                        if (
                                            auth_activity["detected"]
                                            and curr == target_netloc
                                        ):
                                            logger.info(
                                                "Detected SSO round-trip (instant bounce). Assuming login complete."
                                            )
                                            await page.wait_for_load_state(
                                                "networkidle"
                                            )
                                            break

                                        await page.wait_for_timeout(500)
                                        checks += 1

                                    # Allow final content to settle
                                    await page.wait_for_load_state("networkidle")
                            else:
                                # Started elsewhere (e.g. login_url). Just wait for target.
                                logger.info(
                                    f"Waiting for redirect back to {target_netloc}..."
                                )
                                await page.wait_for_url(
                                    lambda url: urlparse(url).netloc == target_netloc,
                                    timeout=self.config.timeout_seconds * 1000,
                                )
                                await page.wait_for_load_state("networkidle")

                            logger.info("Login completed successfully!")

                        except Exception as e:
                            # Catch browser closing (Manual Override)
                            if "Target closed" in str(e) or "Page closed" in str(e):
                                logger.warning(
                                    "Browser closed by user. Assuming manual login complete."
                                )
                                logger.warning(
                                    "Note: If you closed the browser before redirection back to the target content, cookies may be incomplete."
                                )
                            else:
                                logger.warning(f"Browser interaction interrupted: {e}")

                        # Save storage state
                        try:
                            storage_state = await context.storage_state()
                            self._save_storage_state(storage_state)
                        except Exception as e:
                            logger.warning(f"Could not save storage state: {e}")

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
            # Update request.cookies so CookiesMiddleware handles formatting and merging
            # request.cookies is a list or dict, we ensure it's treated as dict
            if hasattr(request, "cookies"):
                # Scrapy Request cookies can be dict or list of dicts.
                # Safest is to update the dict.
                if not request.cookies:
                    request.cookies = {}
                if isinstance(request.cookies, dict):
                    request.cookies.update(session.cookies)
                elif isinstance(request.cookies, list):
                    pass

            # Update request.cookies (dict API)
            request.cookies = session.cookies

            # CRITICAL: Also set the raw Cookie header directly.
            # This ensures cookies are sent even if CookiesMiddleware runs before this
            # or if it ignores request.cookies updates.
            cookie_header = "; ".join([f"{k}={v}" for k, v in session.cookies.items()])
            request.headers["Cookie"] = cookie_header

            # Enforce the same User-Agent as used in Playwright
            # This prevents session invalidation due to UA mismatch
            request.headers["User-Agent"] = self.config.user_agent

        return request

    def is_auth_required(self, response: Response) -> bool:
        """Check if response indicates SSO authentication is required."""
        # Standard checks
        if response.status in {401, 403}:
            return True

        # Ignore 404s (e.g. missing robots.txt on auth domain)
        if response.status == 404:  # noqa: PLR2004
            return False

        # Check if we landed ON an auth page (e.g. via 200 OK or followed redirect)
        current_url = response.url.lower()

        # Ignore robots.txt checks
        if current_url.endswith("robots.txt"):
            return False

        if any(
            indicator in current_url
            for indicator in [
                "auth.cern.ch",
                "login.cern.ch",
                "keycloak",
                "/auth/realms/",
                "signin",
                "sso",
            ]
        ):
            logger.info(f"Landed on auth URL: {current_url}")
            return True

        # Check for SSO redirect (3xx)
        if response.status in {301, 302, 303, 307, 308}:
            loc_header = response.headers.get(b"Location", b"")
            location = ""
            if loc_header:
                try:
                    location = loc_header.decode("utf-8", errors="ignore").lower()
                except Exception:
                    location = str(loc_header).lower()

            logger.debug(f"Checking Redirect {response.status} to: {location}")

            # CERN SSO patterns
            if any(
                indicator in location
                for indicator in [
                    "auth.cern.ch",
                    "login.cern.ch",
                    "keycloak",
                    "/auth/realms/",
                    "signin",
                    "sso",
                ]
            ):
                logger.info(f"Auth redirect detected to: {location}")
                return True

        return False

    def has_valid_storage_state(self) -> bool:
        """Check if we have saved storage state."""
        return self._storage_state is not None and bool(
            self._storage_state.get("cookies")
        )

    def is_auth_domain(self, url: str) -> bool:
        """Check if URL belongs to the auth provider."""
        # Check against configured login_url domain if available
        if self.config.login_url:
            login_netloc = urlparse(self.config.login_url).netloc
            if login_netloc and login_netloc in url:
                return True

        # Check against common SSO patterns
        # This list matches is_auth_required logic
        url_lower = url.lower()
        return bool(
            any(
                indicator in url_lower
                for indicator in [
                    "auth.cern.ch",
                    "login.cern.ch",
                    "keycloak",
                    "/auth/realms/",
                    "signin",
                    "sso",
                ]
            )
        )
