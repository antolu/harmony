from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import harmony.providers.web_crawler.auth._cli as cli_module
from harmony.providers.web_crawler.auth._config import BasicAuthConfig, OIDCAuthConfig
from harmony.providers.web_crawler.auth.providers._basic import BasicAuth
from harmony.providers.web_crawler.auth.providers._oidc import OIDCAuth


def test_cmd_auth_status_displays_oidc_provider_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = OIDCAuthConfig(
        name="my-oidc",
        domains=[r".*\.example\.com"],
        issuer_url="https://auth.example.com",
        client_id="client",
    )
    provider = OIDCAuth(config)

    registry = MagicMock()
    registry.get_providers.return_value = [provider]
    registry.get_sessions.return_value = {}

    monkeypatch.setattr(cli_module, "load_auth_config", lambda *_: MagicMock())
    monkeypatch.setattr(cli_module, "_make_cli_session_writer", lambda: None)
    monkeypatch.setattr(cli_module, "AuthProviderRegistry", lambda *a, **k: registry)

    exit_code = cli_module.cmd_auth_status()
    assert exit_code == 0


def test_basic_auth_provider_config_has_no_name_attribute() -> None:
    config = BasicAuthConfig(domains=[r".*\.example\.com"], username="u", password="p")
    provider = BasicAuth(config)
    assert not hasattr(provider.config, "name")
