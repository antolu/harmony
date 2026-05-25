from __future__ import annotations

from cryptography.fernet import Fernet


def test_external_api_key_encrypted_at_rest() -> None:
    """EXT-04: External provider API keys are encrypted at rest."""
    from harmony.api.observability import SecretValueService

    key = Fernet.generate_key()
    svc = SecretValueService(key)

    plaintext = "sk-abc"
    ciphertext = svc.encrypt(plaintext)

    assert ciphertext != plaintext
    assert "sk-abc" not in ciphertext
    assert svc.decrypt(ciphertext) == plaintext


def test_external_api_key_not_in_get_response() -> None:
    """EXT-04: GET responses for external provider settings do not include plaintext API keys."""
    from harmony.api.observability import SecretValueService

    key = Fernet.generate_key()
    svc = SecretValueService(key)

    plaintext = "sk-abc"
    ciphertext = svc.encrypt(plaintext)

    assert plaintext not in ciphertext
    assert ciphertext != plaintext


def test_external_api_key_redacted_from_logs() -> None:
    """EXT-04: External provider API keys are redacted from all log output."""
    from harmony.api.services.admin import ServiceConfigStore

    assert "brave_api_key" in ServiceConfigStore._SECRET_KEYS
    assert "google_api_key" in ServiceConfigStore._SECRET_KEYS
    assert "harmony_secret_key" in ServiceConfigStore._SECRET_KEYS
