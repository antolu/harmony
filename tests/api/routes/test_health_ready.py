from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from harmony.api.main import app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def test_health_returns_ok_without_dependency_check(client: AsyncClient) -> None:
    """OBS-03: GET /health returns 200 {status: ok} with no dependency checks."""
    import asyncio

    response = asyncio.get_event_loop().run_until_complete(client.get("/health"))
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "elasticsearch" not in data


async def test_health_returns_ok_async(client: AsyncClient) -> None:
    """OBS-03: GET /health returns 200 {status: ok}."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "elasticsearch" not in data


async def test_ready_returns_dependency_status_per_dep(client: AsyncClient) -> None:
    """OBS-03: GET /ready returns per-dependency status dict when all healthy."""
    app.state.es_service = AsyncMock()
    app.state.es_service.health_check = AsyncMock(return_value=True)
    app.state.qdrant_service = None
    app.state.redis_client = AsyncMock()
    app.state.redis_client.ping = AsyncMock(return_value=True)
    app.state.db_pool = MagicMock()
    conn_mock = AsyncMock()
    conn_mock.__aenter__ = AsyncMock(return_value=conn_mock)
    conn_mock.__aexit__ = AsyncMock(return_value=None)
    app.state.db_pool.connection = MagicMock(return_value=conn_mock)

    with patch(
        "harmony.api.main._check_ollama_health", new=AsyncMock(return_value=True)
    ):
        response = await client.get("/ready")

    assert response.status_code == 200
    data = response.json()
    assert "dependencies" in data
    assert "elasticsearch" in data["dependencies"]
    assert "postgres" in data["dependencies"]
    assert "redis" in data["dependencies"]


async def test_ready_returns_503_when_es_down(client: AsyncClient) -> None:
    """OBS-03: GET /ready returns 503 when Elasticsearch is unreachable."""
    app.state.es_service = AsyncMock()
    app.state.es_service.health_check = AsyncMock(return_value=False)
    app.state.qdrant_service = None
    app.state.redis_client = AsyncMock()
    app.state.redis_client.ping = AsyncMock(return_value=True)
    app.state.db_pool = MagicMock()
    conn_mock = AsyncMock()
    conn_mock.__aenter__ = AsyncMock(return_value=conn_mock)
    conn_mock.__aexit__ = AsyncMock(return_value=None)
    app.state.db_pool.connection = MagicMock(return_value=conn_mock)

    with patch(
        "harmony.api.main._check_ollama_health", new=AsyncMock(return_value=True)
    ):
        response = await client.get("/ready")

    assert response.status_code == 503
