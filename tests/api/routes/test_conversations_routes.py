from __future__ import annotations

from fastapi import APIRouter

from harmony.api.routes.conversations import router


def test_router_is_apirouter() -> None:
    assert isinstance(router, APIRouter)


def test_router_has_list_route() -> None:
    paths = {r.path for r in router.routes}  # type: ignore
    assert "/" in paths


def test_router_has_detail_route() -> None:
    paths = {r.path for r in router.routes}  # type: ignore
    assert "/{conversation_id}" in paths


def test_router_has_title_route() -> None:
    paths = {r.path for r in router.routes}  # type: ignore
    assert "/{conversation_id}/title" in paths


def test_router_has_delete_route() -> None:
    routes_by_path: dict[str, set[str]] = {}
    for r in router.routes:
        routes_by_path.setdefault(r.path, set()).update(r.methods or set())  # type: ignore
    assert "DELETE" in routes_by_path.get("/{conversation_id}", set())


def test_list_route_methods() -> None:
    routes_by_path: dict[str, set[str]] = {}
    for r in router.routes:
        routes_by_path.setdefault(r.path, set()).update(r.methods or set())  # type: ignore
    assert "GET" in routes_by_path.get("/", set())


def test_router_has_hydrate_route() -> None:
    routes_by_path: dict[str, set[str]] = {}
    for r in router.routes:
        routes_by_path.setdefault(r.path, set()).update(r.methods or set())  # type: ignore
    assert "POST" in routes_by_path.get("/sources/hydrate", set())


def test_detail_route_methods() -> None:
    routes_by_path: dict[str, set[str]] = {}
    for r in router.routes:
        routes_by_path.setdefault(r.path, set()).update(r.methods or set())  # type: ignore
    assert "GET" in routes_by_path.get("/{conversation_id}", set())


def test_title_route_methods() -> None:
    routes_by_path: dict[str, set[str]] = {}
    for r in router.routes:
        routes_by_path.setdefault(r.path, set()).update(r.methods or set())  # type: ignore
    assert "PATCH" in routes_by_path.get("/{conversation_id}/title", set())
