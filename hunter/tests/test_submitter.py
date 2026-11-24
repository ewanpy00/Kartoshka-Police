import io
import json
import logging
import urllib.error

import pytest

from app import submitter as module
from app.submitter import Submitter


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def posts(monkeypatch):
    requests = []

    def urlopen(request, timeout):
        requests.append(request)
        return Response()

    monkeypatch.setattr(module.urllib.request, "urlopen", urlopen)
    return requests


class Clock:
    now = 0.0

    def __call__(self) -> float:
        return self.now


def make(per_minute=6, token="secret", clock=None):
    return Submitter("http://core:8000/", token, per_minute, clock or Clock())


def test_post_carries_the_token_and_the_hunter_deep_body(posts):
    assert make().submit("pay-tamm.com") is True
    request = posts[0]
    assert request.full_url == "http://core:8000/v1/check"
    assert request.get_header("Authorization") == "Bearer secret"
    assert json.loads(request.data) == {"url": "https://pay-tamm.com/", "source": "hunter", "mode": "deep"}


def test_wildcard_prefix_is_stripped(posts):
    make().submit("*.pay-tamm.com")
    assert json.loads(posts[0].data)["url"] == "https://pay-tamm.com/"


def test_a_domain_is_submitted_once_even_as_a_wildcard(posts):
    submitter = make()
    submitter.submit("pay-tamm.com")
    assert submitter.submit("*.pay-tamm.com") is False
    assert len(posts) == 1


def test_cap_drops_extra_matches_until_the_minute_passes(posts, caplog):
    clock = Clock()
    submitter = make(per_minute=2, clock=clock)
    with caplog.at_level(logging.INFO, logger="hunter"):
        results = [submitter.submit(f"tamm-{i}.com") for i in range(3)]
    assert results == [True, True, False]
    assert "dropped domain=tamm-2.com" in caplog.text
    clock.now = 61
    assert submitter.submit("tamm-2.com") is True
    assert len(posts) == 3


def test_seen_set_is_bounded(posts, monkeypatch):
    monkeypatch.setattr(module, "SEEN_LIMIT", 2)
    submitter = make(per_minute=10)
    for name in ("a-tamm.com", "b-tamm.com", "c-tamm.com"):
        submitter.submit(name)
    assert list(submitter.seen) == ["b-tamm.com", "c-tamm.com"]


def test_empty_token_disables_submission_and_logs_once(posts, caplog):
    with caplog.at_level(logging.WARNING, logger="hunter"):
        submitter = make(token="")
        assert submitter.submit("pay-tamm.com") is False
        assert submitter.submit("other-tamm.com") is False
    assert posts == []
    assert caplog.text.count("submission to core is disabled") == 1


def test_failed_post_is_logged_with_status_and_never_raises(monkeypatch, caplog):
    def refuse(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "denied", {}, io.BytesIO())

    monkeypatch.setattr(module.urllib.request, "urlopen", refuse)
    with caplog.at_level(logging.WARNING, logger="hunter"):
        assert make().submit("pay-tamm.com") is False
    assert "status=401" in caplog.text
    assert "secret" not in caplog.text


def test_transport_error_logs_the_class_name_only(monkeypatch, caplog):
    def down(request, timeout):
        raise ConnectionRefusedError("http://core:8000 Bearer secret")

    monkeypatch.setattr(module.urllib.request, "urlopen", down)
    with caplog.at_level(logging.WARNING, logger="hunter"):
        assert make().submit("pay-tamm.com") is False
    assert "ConnectionRefusedError" in caplog.text
    assert "secret" not in caplog.text
