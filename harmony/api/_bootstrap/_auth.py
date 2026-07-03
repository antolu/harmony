from __future__ import annotations

import dataclasses
import typing

import structlog
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key,
    load_pem_public_key,
)

from harmony.db.redis_client import get_async_redis

from ..auth._middleware import generate_rsa_key_pair

if typing.TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.rsa import (
        RSAPrivateKey,
        RSAPublicKey,
    )
    from redis.asyncio import Redis

    from harmony.services.admin import ServiceConfigStore

logger = structlog.get_logger(__name__)


@dataclasses.dataclass(frozen=True)
class AuthComponents:
    jwt_private_key: RSAPrivateKey
    jwt_public_key: RSAPublicKey
    auth_mode: str
    harmony_public_url: str
    redis_client: Redis


async def init_auth(service_config: ServiceConfigStore) -> AuthComponents:
    private_pem = await service_config.get("jwt_private_key_pem")
    public_pem = await service_config.get("jwt_public_key_pem")
    if not private_pem or not public_pem:
        private_pem, public_pem = generate_rsa_key_pair()
        await service_config.set("jwt_private_key_pem", private_pem, validated=True)
        await service_config.set("jwt_public_key_pem", public_pem, validated=True)
        logger.info("Generated new RSA key pair for JWT signing")
    jwt_private_key = typing.cast(
        "RSAPrivateKey",
        load_pem_private_key(
            private_pem.encode(), password=None, backend=default_backend()
        ),
    )
    jwt_public_key = typing.cast(
        "RSAPublicKey",
        load_pem_public_key(public_pem.encode(), backend=default_backend()),
    )
    auth_mode = await service_config.get("auth_mode") or "optional"

    harmony_public_url = await service_config.get("harmony_public_url") or ""
    redis_client = await get_async_redis()
    logger.info(f"JWT authentication initialized (auth_mode={auth_mode})")
    return AuthComponents(
        jwt_private_key=jwt_private_key,
        jwt_public_key=jwt_public_key,
        auth_mode=auth_mode,
        harmony_public_url=harmony_public_url,
        redis_client=redis_client,
    )
