from __future__ import annotations

import pytest


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_oidc_group_mapping_derives_harmony_roles() -> None:
    """AUTHZ-02: OIDC group claims map to normalized harmony_role values without broad fallback."""


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_url_domain_policy_derives_acl_from_path() -> None:
    """AUTHZ-02: URL/domain ACL provider derives access policy from path without broad fallback."""
