from __future__ import annotations


def test_es_state_index_in_defaults() -> None:
    from harmony.api.services.admin import ServiceConfigStore

    assert "es_state_index" in ServiceConfigStore.DEFAULTS


def test_es_state_index_in_env_map() -> None:
    from harmony.api.services.admin import ServiceConfigStore

    assert "es_state_index" in ServiceConfigStore._ENV_MAP


def test_admin_config_has_no_duplicate_es_fields() -> None:
    from harmony.api import admin_config

    settings = admin_config.AdminSettings()
    assert not hasattr(settings, "es_index_base_name"), (
        "es_index_base_name is duplicated in AdminSettings — remove it"
    )
    assert not hasattr(settings, "es_state_index"), (
        "es_state_index is duplicated in AdminSettings — remove it"
    )
    assert not hasattr(settings, "es_host"), (
        "es_host is duplicated in AdminSettings — remove it"
    )
