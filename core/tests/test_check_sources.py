import pytest

from app.api.check import RESERVED_SOURCES, RESIDENT_SOURCES

URL = "https://unknown-site.example/"
AUTH = {"Authorization": "Bearer test-token"}


def post(client, source, headers=None):
    return client.post("/v1/check", json={"url": URL, "source": source, "mode": "fast"}, headers=headers or {})


def test_the_reserved_set_is_the_four_main_sources_plus_batch():
    assert set(RESERVED_SOURCES) == {"hunter", "watchlist", "user_report", "officer", "batch"}
    assert not set(RESERVED_SOURCES) & set(RESIDENT_SOURCES)


@pytest.mark.parametrize("source", RESERVED_SOURCES)
def test_a_reserved_source_without_the_token_is_rejected(client, source):
    assert post(client, source).status_code == 401


@pytest.mark.parametrize("source", RESERVED_SOURCES)
def test_a_reserved_source_with_a_wrong_token_is_rejected(client, source):
    assert post(client, source, {"Authorization": "Bearer nope"}).status_code == 401


@pytest.mark.parametrize("source", RESERVED_SOURCES)
def test_a_reserved_source_with_the_token_is_accepted(client, source):
    assert post(client, source, AUTH).status_code == 200


@pytest.mark.parametrize("source", RESIDENT_SOURCES)
def test_resident_sources_need_no_token(client, source):
    assert post(client, source).status_code == 200


def test_the_default_source_needs_no_token(client):
    assert client.post("/v1/check", json={"url": URL}).status_code == 200
