from __future__ import annotations

import pytest


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_providers_disabled_by_default() -> None:
    """EXT-01: External search providers are disabled by default and require explicit activation."""


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_enabled_provider_requires_api_key() -> None:
    """EXT-01: Enabling an external provider requires a valid API key gate to be satisfied."""


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_enabled_external_results_merge_before_ranking() -> None:
    """EXT-02: When enabled, external results are merged with internal results before ranking."""


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_external_results_carry_source_type_and_provider_fields() -> None:
    """EXT-03: External results include source_type and provider provenance fields."""


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_external_results_obey_harmony_group_policy() -> None:
    """EXT-03: External results are filtered by the caller's harmony group policy."""


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_provider_result_count_limit_enforced() -> None:
    """EXT-05: Provider result count limit is enforced before API calls and during merge."""
