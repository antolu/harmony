from __future__ import annotations

import pytest
from harmony.api.auth._oidc_core import (  # noqa: PLC2701
    build_pkce_pair,
    discover_oidc_endpoints,
)


@pytest.mark.asyncio
async def test_pkce_challenge() -> None:
    verifier, challenge = build_pkce_pair()
    assert isinstance(verifier, str)
    assert len(verifier) >= 32
    assert isinstance(challenge, str)
    assert len(challenge) > 0


@pytest.mark.asyncio
async def test_discover_oidc_endpoints() -> None:
    issuer_url = "https://example.com/auth/realms/test"
    auth_endpoint, token_endpoint = await discover_oidc_endpoints(issuer_url)
    assert isinstance(auth_endpoint, str)
    assert isinstance(token_endpoint, str)
