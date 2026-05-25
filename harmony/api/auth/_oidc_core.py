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


async def discover_oidc_endpoints(issuer_url: str) -> tuple[str, str]:
    """Fetch OIDC token and authorization endpoints from discovery document.

    Returns (token_endpoint, auth_endpoint).
    Raises ValueError if the token_endpoint hostname does not match the issuer
    hostname or if the token_endpoint uses http:// when the issuer uses https://.
    """
    url = f"{issuer_url.rstrip('/')}/.well-known/openid-configuration"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        doc = resp.json()

    token_endpoint = doc["token_endpoint"]
    issuer_parsed = urlparse(issuer_url)
    token_parsed = urlparse(token_endpoint)

    issuer_netloc = issuer_parsed.netloc.lower()
    token_netloc = token_parsed.netloc.lower()

    if token_netloc != issuer_netloc:
        msg = (
            f"OIDC discovery token_endpoint hostname {token_netloc!r} does not match"
            f" issuer hostname {issuer_netloc!r} — possible SSRF in discovery document"
        )
        raise ValueError(msg)

    if issuer_parsed.scheme == "https" and token_parsed.scheme != "https":
        msg = (
            f"OIDC discovery token_endpoint must use https:// when issuer uses https://"
            f" (got {token_parsed.scheme!r})"
        )
        raise ValueError(msg)

    return token_endpoint, doc.get("authorization_endpoint", "")


async def fetch_token(token_endpoint: str, data: dict, timeout: int = 15) -> dict:
    """Exchange authorization code or refresh token for OIDC token payload."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(token_endpoint, data=data, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
