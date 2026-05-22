from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from harmony.api.services import ExternalSearchService


def _make_config(overrides: dict | None = None) -> MagicMock:
    defaults = {
        "external_search_enabled": "false",
        "external_search_brave_enabled": "false",
        "external_search_google_enabled": "false",
        "external_search_allowed_roles": "admin",
        "external_search_brave_limit": "5",
        "external_search_google_limit": "5",
        "google_search_cx": "",
        "brave_api_key": "",
        "google_api_key": "",
        "data_residency_mode": "false",
    }
    if overrides:
        defaults.update(overrides)

    config = MagicMock()
    config.get = AsyncMock(side_effect=lambda key: defaults.get(key, ""))
    return config


def _make_secret_service(key: bytes | None = None) -> MagicMock:
    if key is None:
        key = Fernet.generate_key()
    fernet = Fernet(key)
    svc = MagicMock()
    svc.encrypt = lambda p: fernet.encrypt(p.encode()).decode()
    svc.decrypt = lambda c: fernet.decrypt(c.encode()).decode()
    return svc


def _make_authz_context(roles: list[str] | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.harmony_roles = roles or []
    ctx.trace_id = "test-trace"
    return ctx


@pytest.mark.asyncio
async def test_providers_disabled_by_default() -> None:
    config = _make_config()
    svc = ExternalSearchService(
        service_config=config, secret_service=_make_secret_service()
    )
    result = await svc.is_allowed(None, request_toggle=True)
    assert result is False


@pytest.mark.asyncio
async def test_data_residency_mode_skips_external_search() -> None:
    key = Fernet.generate_key()
    fernet = Fernet(key)
    encrypted_key = fernet.encrypt(b"my-brave-key").decode()

    config = _make_config({
        "data_residency_mode": "true",
        "external_search_enabled": "true",
        "external_search_brave_enabled": "true",
        "brave_api_key": encrypted_key,
        "external_search_allowed_roles": "admin",
    })
    svc = ExternalSearchService(
        service_config=config, secret_service=_make_secret_service(key)
    )
    authz = _make_authz_context(["admin"])

    result = await svc.is_allowed(authz, request_toggle=True)
    assert result is False


@pytest.mark.asyncio
async def test_enabled_provider_requires_api_key() -> None:
    config = _make_config({
        "external_search_enabled": "true",
        "external_search_brave_enabled": "true",
        "brave_api_key": "",
        "external_search_allowed_roles": "admin",
    })
    svc = ExternalSearchService(
        service_config=config, secret_service=_make_secret_service()
    )
    authz = _make_authz_context(["admin"])

    results = await svc.fetch_external_results("test query", authz, request_toggle=True)
    assert results == []


@pytest.mark.asyncio
async def test_enabled_external_results_merge_before_ranking() -> None:
    from kv_search import SearchHit

    key = Fernet.generate_key()
    fernet = Fernet(key)
    encrypted_key = fernet.encrypt(b"my-brave-key").decode()

    config = _make_config({
        "external_search_enabled": "true",
        "external_search_brave_enabled": "true",
        "brave_api_key": encrypted_key,
        "external_search_allowed_roles": "admin",
    })
    secret_svc = _make_secret_service(key)
    svc = ExternalSearchService(service_config=config, secret_service=secret_svc)
    authz = _make_authz_context(["admin"])

    mock_hits = [
        SearchHit(
            path="https://example.com/1",
            score=0.0,
            metadata={
                "source_type": "external",
                "provider": "brave",
                "title": "A",
                "content": "B",
            },
        ),
        SearchHit(
            path="https://example.com/2",
            score=0.0,
            metadata={
                "source_type": "external",
                "provider": "brave",
                "title": "C",
                "content": "D",
            },
        ),
    ]

    with patch("harmony.api.services._external_search.BraveProvider") as MockBrave:
        instance = MockBrave.return_value
        instance.search = AsyncMock(return_value=mock_hits)
        results = await svc.fetch_external_results("test", authz, request_toggle=True)

    assert len(results) == 2


@pytest.mark.asyncio
async def test_external_results_carry_source_type_and_provider_fields() -> None:
    from kv_search import SearchHit

    key = Fernet.generate_key()
    fernet = Fernet(key)
    encrypted_key = fernet.encrypt(b"my-brave-key").decode()

    config = _make_config({
        "external_search_enabled": "true",
        "external_search_brave_enabled": "true",
        "brave_api_key": encrypted_key,
        "external_search_allowed_roles": "admin",
    })
    secret_svc = _make_secret_service(key)
    svc = ExternalSearchService(service_config=config, secret_service=secret_svc)
    authz = _make_authz_context(["admin"])

    mock_hit = SearchHit(
        path="https://example.com/1",
        score=0.0,
        metadata={
            "source_type": "external",
            "provider": "brave",
            "title": "T",
            "content": "C",
        },
    )

    with patch("harmony.api.services._external_search.BraveProvider") as MockBrave:
        instance = MockBrave.return_value
        instance.search = AsyncMock(return_value=[mock_hit])
        results = await svc.fetch_external_results("test", authz, request_toggle=True)

    assert len(results) == 1
    assert results[0].metadata.get("source_type") == "external"
    assert results[0].metadata.get("provider") == "brave"


@pytest.mark.asyncio
async def test_external_results_obey_harmony_group_policy() -> None:
    key = Fernet.generate_key()
    fernet = Fernet(key)
    encrypted_key = fernet.encrypt(b"my-brave-key").decode()

    config = _make_config({
        "external_search_enabled": "true",
        "external_search_brave_enabled": "true",
        "brave_api_key": encrypted_key,
        "external_search_allowed_roles": "admin",
    })
    secret_svc = _make_secret_service(key)
    svc = ExternalSearchService(service_config=config, secret_service=secret_svc)
    authz = _make_authz_context(["read_only"])

    results = await svc.fetch_external_results("test", authz, request_toggle=True)
    assert results == []


@pytest.mark.asyncio
async def test_provider_result_count_limit_enforced() -> None:
    from kv_search import SearchHit

    key = Fernet.generate_key()
    fernet = Fernet(key)
    encrypted_key = fernet.encrypt(b"my-brave-key").decode()

    config = _make_config({
        "external_search_enabled": "true",
        "external_search_brave_enabled": "true",
        "brave_api_key": encrypted_key,
        "external_search_allowed_roles": "admin",
        "external_search_brave_limit": "3",
    })
    secret_svc = _make_secret_service(key)
    svc = ExternalSearchService(service_config=config, secret_service=secret_svc)
    authz = _make_authz_context(["admin"])

    three_hits = [
        SearchHit(
            path=f"https://example.com/{i}",
            score=0.0,
            metadata={"source_type": "external", "provider": "brave"},
        )
        for i in range(3)
    ]

    with patch("harmony.api.services._external_search.BraveProvider") as MockBrave:
        instance = MockBrave.return_value
        instance.search = AsyncMock(return_value=three_hits)
        results = await svc.fetch_external_results("test", authz, request_toggle=True)

    assert len(results) == 3


@pytest.mark.asyncio
async def test_get_default_toggle_for_roles_returns_true_when_role_configured_on() -> (
    None
):
    config = _make_config()
    config.get = AsyncMock(
        side_effect=lambda key: "on" if key == "external_search_default_admin" else ""
    )
    svc = ExternalSearchService(
        service_config=config, secret_service=_make_secret_service()
    )

    result = await svc.get_default_toggle_for_roles(["admin"])
    assert result is True


@pytest.mark.asyncio
async def test_get_default_toggle_for_roles_returns_false_when_no_config() -> None:
    config = _make_config()
    config.get = AsyncMock(return_value="")
    svc = ExternalSearchService(
        service_config=config, secret_service=_make_secret_service()
    )

    result = await svc.get_default_toggle_for_roles(["admin", "read_only"])
    assert result is False


@pytest.mark.asyncio
async def test_get_default_toggle_for_roles_returns_false_when_role_configured_off() -> (
    None
):
    config = _make_config()
    config.get = AsyncMock(
        side_effect=lambda key: (
            "off" if key == "external_search_default_read_only" else ""
        )
    )
    svc = ExternalSearchService(
        service_config=config, secret_service=_make_secret_service()
    )

    result = await svc.get_default_toggle_for_roles(["read_only"])
    assert result is False
