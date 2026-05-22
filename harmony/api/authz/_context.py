from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from harmony.api.models.user import AnonymousIdentity, UserIdentity


@dataclasses.dataclass(frozen=True)
class AuthorizationContext:
    user_id: str
    harmony_roles: list[str]
    harmony_groups: list[str]
    raw_claims: dict[str, object]
    trace_id: str
    auth_mode: str

    @classmethod
    def from_user_identity(
        cls,
        user: UserIdentity | AnonymousIdentity,
        *,
        trace_id: str,
        auth_mode: str,
    ) -> AuthorizationContext:
        raw_claims = getattr(user, "raw_claims", {})
        harmony_groups = [str(g) for g in raw_claims.get("groups", [])]  # type: ignore[union-attr]
        return cls(
            user_id=user.id,
            harmony_roles=list(user.harmony_roles),
            harmony_groups=harmony_groups,
            raw_claims=dict(raw_claims),
            trace_id=trace_id,
            auth_mode=auth_mode,
        )
