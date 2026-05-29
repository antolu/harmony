from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlparse

import httpx


def build_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) using S256."""
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


async def discover_oidc_endpoints(
    issuer_url: str,
    internal_url: str = "",
) -> tuple[str, str]:
    """Fetch OIDC token and authorization endpoints from discovery document.

    Returns (token_endpoint, auth_endpoint) using issuer_url hostnames (public).

    When internal_url is provided (Docker split-hostname), the HTTP fetch uses
    internal_url but the returned endpoints are rewritten to use issuer_url so
    the browser can reach the auth endpoint and JWT iss validation passes.

    Raises ValueError if https is violated.
    """
    fetch_base = (internal_url or issuer_url).rstrip("/")
    canonical_base = issuer_url.rstrip("/")

    url = f"{fetch_base}/.well-known/openid-configuration"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        doc = resp.json()

    # Rewrite endpoints from internal hostname to canonical (public) hostname.
    # This is safe — we fetched from our own known-good internal URL.
    token_endpoint = doc["token_endpoint"].replace(fetch_base, canonical_base, 1)
    auth_endpoint = doc.get("authorization_endpoint", "").replace(
        fetch_base, canonical_base, 1
    )

    issuer_parsed = urlparse(canonical_base)
    token_parsed = urlparse(token_endpoint)

    if issuer_parsed.scheme == "https" and token_parsed.scheme != "https":
        msg = (
            f"OIDC discovery token_endpoint must use https:// when issuer uses https://"
            f" (got {token_parsed.scheme!r})"
        )
        raise ValueError(msg)

    return token_endpoint, auth_endpoint


async def fetch_token(token_endpoint: str, data: dict, timeout: int = 15) -> dict:
    """Exchange authorization code or refresh token for OIDC token payload."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(token_endpoint, data=data, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
