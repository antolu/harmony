from __future__ import annotations

import base64
import hashlib


def test_build_pkce_pair_returns_tuple() -> None:
    from harmony.api.auth._oidc_core import build_pkce_pair  # noqa: PLC2701

    result = build_pkce_pair()
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_build_pkce_pair_verifier_length() -> None:
    from harmony.api.auth._oidc_core import build_pkce_pair  # noqa: PLC2701

    verifier, _ = build_pkce_pair()
    assert len(verifier) >= 32


def test_build_pkce_pair_challenge_is_s256_of_verifier() -> None:
    from harmony.api.auth._oidc_core import build_pkce_pair  # noqa: PLC2701

    verifier, challenge = build_pkce_pair()
    digest = hashlib.sha256(verifier.encode()).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    assert challenge == expected


def test_build_pkce_pair_challenge_no_padding() -> None:
    from harmony.api.auth._oidc_core import build_pkce_pair  # noqa: PLC2701

    _, challenge = build_pkce_pair()
    assert "=" not in challenge


def test_user_identity_from_jwt_full_payload() -> None:
    from harmony.api.models.user import UserIdentity

    payload = {
        "user_id": "u1",
        "sub": "s1",
        "email": "e@e.com",
        "display_name": "E",
        "harmony_role": "admin",
    }
    identity = UserIdentity.from_jwt(payload)
    assert identity.id == "u1"
    assert identity.sub == "s1"
    assert identity.email == "e@e.com"
    assert identity.display_name == "E"
    assert identity.harmony_role == "admin"


def test_user_identity_from_jwt_default_role() -> None:
    from harmony.api.models.user import UserIdentity

    payload = {"user_id": "u2", "sub": "s2"}
    identity = UserIdentity.from_jwt(payload)
    assert identity.harmony_role == "read_only"


def test_anonymous_identity_defaults() -> None:
    from harmony.api.models.user import AnonymousIdentity

    anon = AnonymousIdentity()
    assert anon.id == "anonymous"
    assert not anon.harmony_role
    assert anon.api_key is None


def test_user_oidc_config_dataclass() -> None:
    from harmony.api.auth.user_oidc_client import UserOIDCConfig

    cfg = UserOIDCConfig(
        issuer_url="https://example.com",
        client_id="client",
        client_secret="secret",
        scopes=["openid", "profile"],
    )
    assert cfg.issuer_url == "https://example.com"
    assert cfg.scopes == ["openid", "profile"]


def test_user_oidc_client_build_auth_url() -> None:
    from harmony.api.auth.user_oidc_client import UserOIDCClient, UserOIDCConfig

    cfg = UserOIDCConfig(
        issuer_url="https://idp.example.com",
        client_id="my_client",
        client_secret="secret",
        scopes=["openid", "email"],
    )
    client = UserOIDCClient(cfg)
    client._auth_endpoint = "https://idp.example.com/auth"

    url, verifier = client.build_auth_url(
        redirect_uri="https://app.example.com/callback",
        state="some_state",
    )

    assert "response_type=code" in url
    assert "code_challenge_method=S256" in url
    assert "my_client" in url
    assert isinstance(verifier, str)
    assert len(verifier) >= 32


def test_auth_package_init_exists() -> None:
    import harmony.api.auth  # noqa: F401
