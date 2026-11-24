import re

import pytest
from fastapi.routing import APIWebSocketRoute

from app.main import app

EXPLICIT = [
    ("POST", "/v1/review/{evidence_id}"),
    ("POST", "/v1/intel/feeds"),
    ("POST", "/v1/watchlist/run"),
    ("POST", "/v1/hits"),
    ("GET", "/v1/evidence/{evidence_id}.pdf"),
    ("GET", "/v1/evidence/{evidence_id}.json"),
]


def api_routes() -> list[tuple[str, str]]:
    """Every (method, path template) the mounted app serves. FastAPI 0.165 keeps included routers as wrapper
    objects in `app.routes`, so the OpenAPI path table is the flat list of HTTP routes."""
    return [
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}
    ]


def websocket_paths(routes=None) -> list[str]:
    found = []
    for route in routes if routes is not None else app.routes:
        nested = getattr(getattr(route, "original_router", None), "routes", None)
        if nested is not None:
            found += websocket_paths(nested)
        elif isinstance(route, APIWebSocketRoute):
            found.append(route.path)
    return found


def concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "x", path)


def shape(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def admin_routes() -> list[tuple[str, str]]:
    return [(method, path) for method, path in api_routes() if path.startswith("/v1/admin")]


def test_the_admin_routes_are_found():
    assert len(admin_routes()) >= 20


@pytest.mark.parametrize("header", [None, "Bearer nope", "Bearer "])
def test_every_admin_route_requires_the_token(client, header):
    headers = {"Authorization": header} if header else {}
    for method, path in admin_routes():
        assert client.request(method, concrete(path), headers=headers).status_code == 401, (method, path, header)


@pytest.mark.parametrize("method, template", EXPLICIT)
def test_each_privileged_route_exists_and_requires_the_token(client, method, template):
    assert any((m, shape(p)) == (method, shape(template)) for m, p in api_routes()), (method, template)
    path = concrete(template)
    assert client.request(method, path).status_code == 401
    assert client.request(method, path, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_the_events_socket_is_mounted_exactly_once():
    assert [p for p in websocket_paths() if p.endswith("/events")].__len__() == 1
