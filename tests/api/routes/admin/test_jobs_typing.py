from __future__ import annotations

import typing

import redis.asyncio

from harmony.api.routes.admin import jobs
from harmony.clients import QdrantService


def test_check_collection_stale_qdrant_service_typed() -> None:
    hints = typing.get_type_hints(jobs._check_collection_stale)
    assert hints["qdrant_service"] is QdrantService


def test_poll_job_events_pubsub_typed() -> None:
    hints = typing.get_type_hints(jobs._poll_job_events)
    assert hints["pubsub"] is redis.asyncio.client.PubSub
