from __future__ import annotations

import pytest
from harmony.api.auth.user_oidc_client import UserOIDCClient


@pytest.mark.asyncio
async def test_build_auth_url() -> None:
    client = UserOIDCClient(
        client_id="test-client",
        redirect_uri="https://example.com/auth/callback",
        auth_endpoint="https://idp.example.com/auth",
        scopes="openid profile email",
    )
    url, verifier, state = await client.build_auth_url()
    assert "response_type=code" in url
    assert "code_challenge_method=S256" in url
    assert isinstance(verifier, str)
    assert len(verifier) >= 32
    assert isinstance(state, str)
