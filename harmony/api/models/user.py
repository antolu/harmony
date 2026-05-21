from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UserIdentity:
    """User identity attached to request.state.user."""

    id: str
    sub: str
    email: str | None
    display_name: str | None
    harmony_role: str

    @classmethod
    def from_jwt(cls, payload: dict) -> UserIdentity:
        """Construct from JWT claims."""
        return cls(
            id=payload.get("user_id", ""),
            sub=payload.get("sub", ""),
            email=payload.get("email"),
            display_name=payload.get("display_name"),
            harmony_role=payload.get("harmony_role", "read_only"),
        )


@dataclass
class AnonymousIdentity:
    """Anonymous user (when AUTH_MODE=optional or API key auth)."""

    id: str = "anonymous"
    harmony_role: str = ""
    api_key: str | None = None
