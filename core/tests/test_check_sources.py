import pytest

from app.api.check import OPEN_SOURCES, RESIDENT_SOURCES

URL = "https://unknown-site.example/"
AUTH = {"Authorization": "Bearer test-token"}
PRIVILEGED = ["hunter", "watchlist", "user_report", "officer", "batch", "preview", "pivot", "anything-else"]


def post(client, source, headers=None):
    return client.post("/v1/check", json={"url": URL, "source": source, "mode": "fast"}, headers=headers or {})


def test_the_open_set_is_the_resident_sources_plus_the_default():
    assert set(RESIDENT_SOURCES) == {"browser", "gatekeeper", "share", "resident", "sms"}
    assert set(OPEN_SOURCES) == set(RESIDENT_SOURCES) | {"api"}


@pytest.mark.parametrize("source", OPEN_SOURCES)
def test_open_sources_need_no_token(client, source):
    assert post(client, source).status_code == 200


def test_the_default_source_needs_no_token(client):
    assert client.post("/v1/check", json={"url": URL}).status_code == 200


@pytest.mark.parametrize("source", PRIVILEGED)
def test_any_other_source_without_the_token_is_rejected(client, source):
    assert post(client, source).status_code == 401


@pytest.mark.parametrize("source", PRIVILEGED)
def test_any_other_source_with_a_wrong_token_is_rejected(client, source):
    assert post(client, source, {"Authorization": "Bearer nope"}).status_code == 401


@pytest.mark.parametrize("source", PRIVILEGED)
def test_any_other_source_with_the_token_is_accepted(client, source):
    assert post(client, source, AUTH).status_code == 200
