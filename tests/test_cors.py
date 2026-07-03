from __future__ import annotations

import pytest

from harmony.api._config import Settings


def test_cors_requires_allowed_origins_set() -> None:
    s = Settings()
    assert hasattr(s, "cors_allowed_origins"), (
        "Settings must have cors_allowed_origins field (add it in Plan 02)"
    )
    assert s.cors_allowed_origins == [], (
        "cors_allowed_origins must default to empty list when env var is unset"
    )


def test_cors_startup_validation_fails_when_unset() -> None:
    cors_allowed_origins: list[str] = []

    def validate_cors(origins: list[str]) -> None:
        if not origins:
            msg = "CORS_ALLOWED_ORIGINS must be set — refusing to start with wildcard CORS"
            raise RuntimeError(msg)

    with pytest.raises(RuntimeError):
        validate_cors(cors_allowed_origins)
