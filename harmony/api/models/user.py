from __future__ import annotations

import dataclasses

_JWT_STANDARD_FIELDS = frozenset({
    "user_id",
    "sub",
    "email",
    "display_name",
    "harmony_role",
    "jti",
    "iat",
    "exp",
})


@dataclasses.dataclass
class UserIdentity:
    """User identity attached to request.state.user."""

    id: str
    sub: str
    email: str | None
    display_name: str | None
    harmony_role: str
    harmony_roles: list[str] = dataclasses.field(default_factory=list)
    raw_claims: dict[str, object] = dataclasses.field(default_factory=dict)

    @classmethod
    def from_jwt(cls, payload: dict) -> UserIdentity:
        """Construct from JWT claims."""
        role = payload.get("harmony_role", "read_only")
        raw_claims = {k: v for k, v in payload.items() if k not in _JWT_STANDARD_FIELDS}
        return cls(
            id=payload.get("user_id", ""),
            sub=payload.get("sub", ""),
            email=payload.get("email"),
            display_name=payload.get("display_name"),
            harmony_role=role,
            harmony_roles=[role] if role else [],
            raw_claims=raw_claims,
        )


@dataclasses.dataclass
class AnonymousIdentity:
    """Anonymous user (when AUTH_MODE=optional or API key auth)."""

    id: str = "anonymous"
    harmony_role: str = ""
    api_key: str | None = None
    raw_claims: dict[str, object] = dataclasses.field(default_factory=dict)

    @property
    def harmony_roles(self) -> list[str]:
        return ["anonymous"]
