from __future__ import annotations

import pytest

from harmony.api.auth.user_oidc_client import UserOIDCClient, UserOIDCConfig


@pytest.mark.asyncio
async def test_build_auth_url() -> None:
    cfg = UserOIDCConfig(
        issuer_url="https://idp.example.com",
        client_id="test-client",
        client_secret="secret",
        scopes=["openid", "profile", "email"],
    )
    client = UserOIDCClient(cfg)
    client._auth_endpoint = "https://idp.example.com/auth"

    url, verifier = client.build_auth_url(
        redirect_uri="https://example.com/auth/callback",
        state="some_state",
    )
    assert "response_type=code" in url
    assert "code_challenge_method=S256" in url
    assert isinstance(verifier, str)
    assert len(verifier) >= 32
