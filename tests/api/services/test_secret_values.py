from __future__ import annotations

import pytest


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_external_api_key_encrypted_at_rest() -> None:
    """EXT-04: External provider API keys are encrypted at rest in the configuration store."""


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_external_api_key_not_in_get_response() -> None:
    """EXT-04: GET responses for external provider settings do not include plaintext API keys."""


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_external_api_key_redacted_from_logs() -> None:
    """EXT-04: External provider API keys are redacted from all log output."""
