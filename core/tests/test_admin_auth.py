import re

from app.main import app


def admin_requests():
    """FastAPI nests included routers in `app.routes`, so the flat OpenAPI path table is the route list."""
    return [
        (method.upper(), re.sub(r"\{[^}]+\}", "placeholder", path))
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/v1/admin")
        for method in operations
    ]


def test_every_admin_route_requires_the_token(client):
    requests = admin_requests()
    assert requests
    for method, path in requests:
        assert client.request(method, path).status_code == 401, (method, path)
