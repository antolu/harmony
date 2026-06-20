from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from harmony.api.dependencies import get_current_user
from harmony.api.main import app
from harmony.api.models.user import UserIdentity
from harmony.api.routes.admin.urls import list_urls


def _admin_user() -> UserIdentity:
    return UserIdentity(
        id="u1",
        sub="u1",
        email="a@b.com",
        display_name="A",
        harmony_role="admin",
    )


def test_list_urls_signature_has_at_most_three_params() -> None:
    params = inspect.signature(list_urls).parameters
    assert len(params) <= 3


def test_list_urls_returns_expected_shape() -> None:
    es_client = AsyncMock()
    es_client.search = AsyncMock(
        return_value={
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_id": "abc",
                        "_source": {
                            "url": "https://example.com/x",
                            "domain": "example.com",
                            "language": "en",
                        },
                    }
                ],
            }
        }
    )
    es_service = MagicMock()
    es_service.client = es_client
    app.state.es_service = es_service
    app.dependency_overrides[get_current_user] = _admin_user
    try:
        resp = TestClient(app).get(
            "/api/admin/documents",
            params={
                "domain": "x",
                "language": "en",
                "query": "y",
                "limit": 10,
                "offset": 0,
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"urls", "total"}
    assert body["total"] == 1
    assert body["urls"][0]["id"] == "abc"
