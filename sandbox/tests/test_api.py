import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as client:
        yield client


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


@pytest.mark.parametrize("url", ["ftp://example.com/file", "file:///etc/passwd", "javascript:alert(1)", "example.com"])
def test_non_http_url_is_rejected(client, url):
    assert client.post("/capture", json={"url": url}).status_code == 422


@pytest.mark.parametrize("url", ["http://host.docker.internal:8000/", "http://169.254.169.254/", "http://core:8000/"])
def test_internal_start_url_is_rejected(client, url):
    assert client.post("/capture", json={"url": url}).status_code == 422
