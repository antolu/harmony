from __future__ import annotations

import base64
import hashlib
import secrets

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
    """
    url = f"{issuer_url.rstrip('/')}/.well-known/openid-configuration"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        doc = resp.json()
    return doc["token_endpoint"], doc.get("authorization_endpoint", "")


async def fetch_token(token_endpoint: str, data: dict, timeout: int = 15) -> dict:
    """Exchange authorization code or refresh token for OIDC token payload."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(token_endpoint, data=data, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
