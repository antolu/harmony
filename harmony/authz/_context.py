from __future__ import annotations

import dataclasses
import typing

if typing.TYPE_CHECKING:
    from harmony.models import AnonymousIdentity, UserIdentity


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
        raw_claims = user.raw_claims
        groups_raw = raw_claims.get("groups", [])
        harmony_groups = (
            [str(g) for g in groups_raw] if isinstance(groups_raw, list) else []
        )
        return cls(
            user_id=user.id,
            harmony_roles=list(user.harmony_roles),
            harmony_groups=harmony_groups,
            raw_claims=dict(raw_claims),
            trace_id=trace_id,
            auth_mode=auth_mode,
        )
