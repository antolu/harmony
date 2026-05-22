from __future__ import annotations

import os
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet

if TYPE_CHECKING:
    from harmony.api.services.admin._service_config import ServiceConfigStore

_SECRET_KEY_CONFIG_KEY = "harmony_secret_key"


class SecretValueService:
    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    @classmethod
    async def from_env_or_db(
        cls, service_config: ServiceConfigStore
    ) -> SecretValueService:
        env_key = os.environ.get("HARMONY_SECRET_KEY", "").strip()
        if env_key:
            return cls(env_key.encode())

        db_key = await service_config.get(_SECRET_KEY_CONFIG_KEY)
        if db_key:
            return cls(db_key.encode())

        new_key = Fernet.generate_key()
        await service_config.set(
            _SECRET_KEY_CONFIG_KEY, new_key.decode(), validated=True
        )
        return cls(new_key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()
