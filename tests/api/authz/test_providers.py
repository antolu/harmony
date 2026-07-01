from __future__ import annotations

from harmony.api.authz import (
    AuthorizationContext,
    AuthorizationProvider,
    HarmonyRoleProvider,
    UrlDomainProvider,
)
from harmony.models import AnonymousIdentity, UserIdentity


def _make_context(  # noqa: PLR0913
    harmony_roles: list[str] | None = None,
    raw_claims: dict | None = None,
    user_id: str = "u1",
    harmony_groups: list[str] | None = None,
    trace_id: str = "t1",
    auth_mode: str = "jwt",
) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user_id,
        harmony_roles=harmony_roles or [],
        harmony_groups=harmony_groups or [],
        raw_claims=raw_claims or {},
        trace_id=trace_id,
        auth_mode=auth_mode,
    )


def test_oidc_group_mapping_derives_harmony_roles() -> None:
    """AUTHZ-02: OIDC group claims map to normalized harmony_role values without broad fallback."""
    payload = {
        "user_id": "u1",
        "sub": "sub1",
        "email": "user@example.com",
        "display_name": "User One",
        "harmony_role": "admin",
        "harmony_groups": ["g1", "g2"],
        "groups": ["g1", "g2"],
    }
    user = UserIdentity.from_jwt(payload)
    assert user.harmony_roles == ["admin"]
    assert user.raw_claims.get("groups") == ["g1", "g2"]

    ctx = AuthorizationContext.from_user_identity(user, trace_id="t1", auth_mode="jwt")
    assert ctx.harmony_roles == ["admin"]
    assert ctx.harmony_groups == ["g1", "g2"]


def test_url_domain_policy_derives_acl_from_path() -> None:
    """AUTHZ-02: URL/domain ACL provider derives access policy from path without broad fallback."""
    provider = UrlDomainProvider({
        "*/internal/*": ["admin"],
        "*/public/*": ["anonymous", "read_only", "admin"],
    })
    context = _make_context(
        harmony_roles=["admin"],
        raw_claims={"request_url": "https://example.com/internal/page"},
    )
    assert provider.get_acl_terms(context) == ["admin"]

    context_public = _make_context(
        harmony_roles=["read_only"],
        raw_claims={"request_url": "https://example.com/public/page"},
    )
    assert provider.get_acl_terms(context_public) == ["anonymous", "read_only", "admin"]


def test_url_domain_provider_returns_roles_for_matching_pattern() -> None:
    provider = UrlDomainProvider({"*/internal/*": ["admin"]})
    context = _make_context(raw_claims={"request_url": "https://host/internal/doc"})
    assert provider.get_acl_terms(context) == ["admin"]


def test_url_domain_provider_returns_empty_when_no_pattern_matches() -> None:
    provider = UrlDomainProvider({"*/internal/*": ["admin"]})
    context = _make_context(raw_claims={"request_url": "https://host/public/doc"})
    assert provider.get_acl_terms(context) == []


def test_harmony_role_provider_returns_roles() -> None:
    context = _make_context(harmony_roles=["admin", "read_only"])
    provider = HarmonyRoleProvider()
    assert provider.get_acl_terms(context) == ["admin", "read_only"]


def test_anonymous_identity_has_anonymous_role() -> None:
    anon = AnonymousIdentity()
    assert anon.harmony_roles == ["anonymous"]


def test_user_identity_from_jwt_populates_roles_and_claims() -> None:
    payload = {
        "user_id": "u1",
        "sub": "sub1",
        "harmony_role": "admin",
        "groups": ["g1", "g2"],
        "jti": "jti1",
        "iat": 1000,
        "exp": 2000,
    }
    user = UserIdentity.from_jwt(payload)
    assert user.harmony_roles == ["admin"]
    assert "groups" in user.raw_claims
    assert user.raw_claims["groups"] == ["g1", "g2"]
    assert "jti" not in user.raw_claims
    assert "iat" not in user.raw_claims
    assert "exp" not in user.raw_claims


def test_authorization_context_from_user_identity() -> None:
    user = UserIdentity.from_jwt({
        "user_id": "u2",
        "sub": "sub2",
        "harmony_role": "read_only",
        "groups": ["grp1"],
    })
    ctx = AuthorizationContext.from_user_identity(user, trace_id="t2", auth_mode="jwt")
    assert ctx.user_id == "u2"
    assert ctx.harmony_roles == ["read_only"]
    assert ctx.harmony_groups == ["grp1"]
    assert ctx.trace_id == "t2"
    assert ctx.auth_mode == "jwt"


def test_authorization_provider_is_protocol() -> None:
    import typing

    assert isinstance(AuthorizationProvider, type | type(typing.Protocol))


def test_url_domain_provider_returns_empty_when_no_request_url() -> None:
    provider = UrlDomainProvider({"*/internal/*": ["admin"]})
    context = _make_context(raw_claims={})
    assert provider.get_acl_terms(context) == []
