"""Public-route limits, the daily spend caps, static serving and the frozen shapes of the Android routes."""
import json
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.testclient import WebSocketDisconnect

from app import budget, cache, events, static
from app.ai import provider
from app.config import Settings
from app.deps import client_ip
from app.schemas import BlocklistResponse, ReportResponse, Verdict

TOKEN = {"Authorization": "Bearer test-token"}
WRONG = {"Authorization": "Bearer nope"}
URL = "https://my-bakery-shop.example/"


class Counters:
    """An in-memory fixed-window counter in place of the Redis limiter."""

    def __init__(self):
        self.counts: dict[str, int] = {}

    def limited(self, key, limit, window_s):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key] > limit

    def exceeded(self, key, limit):
        return self.counts.get(key, 0) > limit

    def ttl(self, key, window_s):
        return window_s - 5


@pytest.fixture
def live_limits(monkeypatch):
    counters = Counters()
    monkeypatch.setattr(cache, "rate_limited", counters.limited)
    monkeypatch.setattr(cache, "rate_exceeded", counters.exceeded)
    monkeypatch.setattr(cache, "rate_ttl", counters.ttl)
    return counters


class FakeRedis:
    def __init__(self):
        self.values: dict[str, int] = {}

    def incr(self, key):
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def expire(self, key, seconds, nx=False):
        return True

    def decr(self, key):
        self.values[key] -= 1

    def get(self, key):
        return self.values.get(key)


@pytest.fixture
def fake_redis(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(cache, "sync_client", lambda: redis)
    return redis


def request_with(headers: dict, host="1.1.1.1") -> Request:
    return Request({"type": "http", "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
                    "client": (host, 1)})


# Client address

def test_client_ip_ignores_the_header_unless_the_proxy_is_trusted():
    request = request_with({"x-real-ip": "9.9.9.9", "x-forwarded-for": "8.8.8.8"})
    assert client_ip(request, Settings(trust_proxy=False)) == "1.1.1.1"
    assert client_ip(request, Settings(trust_proxy=True)) == "9.9.9.9"


def test_client_ip_falls_back_to_the_socket_and_never_reads_forwarded_for():
    assert client_ip(request_with({}), Settings(trust_proxy=True)) == "1.1.1.1"
    assert client_ip(request_with({"x-forwarded-for": "8.8.8.8"}), Settings(trust_proxy=True)) == "1.1.1.1"


# Settings

def test_database_url_scheme_is_rewritten_for_psycopg():
    assert Settings(database_url="postgres://u:p@h:5432/d").database_url == "postgresql+psycopg://u:p@h:5432/d"
    assert Settings(database_url="postgresql://u:p@h/d").database_url == "postgresql+psycopg://u:p@h/d"
    assert Settings(database_url="postgresql+psycopg://u:p@h/d").database_url == "postgresql+psycopg://u:p@h/d"


def test_empty_daily_caps_mean_unset(monkeypatch):
    monkeypatch.setenv("AI_DAILY_CALLS", "")
    monkeypatch.setenv("DEEP_DAILY_CHECKS", "")
    settings = Settings()
    assert settings.ai_daily_calls is None and settings.deep_daily_checks is None
    monkeypatch.setenv("AI_DAILY_CALLS", "200")
    assert Settings().ai_daily_calls == 200


# Limits

def test_check_over_the_address_limit_gets_429_with_retry_after(client, settings, live_limits):
    settings.check_rate_per_min = 2
    body = {"url": URL, "source": "browser"}
    assert [client.post("/v1/check", json=body).status_code for _ in range(2)] == [200, 200]
    limited = client.post("/v1/check", json=body)
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "55"
    assert "detail" in limited.json()


def test_a_valid_write_token_skips_the_address_limit(client, settings, live_limits):
    settings.check_rate_per_min = 1
    body = {"url": URL, "source": "browser"}
    assert [client.post("/v1/check", json=body, headers=TOKEN).status_code for _ in range(3)] == [200] * 3


def test_addresses_are_counted_separately(client, settings, live_limits):
    settings.check_rate_per_min = 1
    settings.trust_proxy = True
    body = {"url": URL, "source": "browser"}
    assert client.post("/v1/check", json=body, headers={"X-Real-IP": "5.5.5.5"}).status_code == 200
    assert client.post("/v1/check", json=body, headers={"X-Real-IP": "6.6.6.6"}).status_code == 200
    assert client.post("/v1/check", json=body, headers={"X-Real-IP": "5.5.5.5"}).status_code == 429


@pytest.mark.parametrize("method, path, setting, window", [
    ("get", "/v1/radar", "read_rate_per_min", "60"),
    ("get", "/v1/blocklist", "blocklist_rate_per_min", "60"),
    ("get", "/v1/blocklist.txt", "blocklist_rate_per_min", "60"),
    ("get", "/v1/check/c_unknown", "read_rate_per_min", "60"),
    ("get", "/v1/reports/r_unknown", "read_rate_per_min", "60"),
    ("get", "/v1/preview/ev_unknown.png", "read_rate_per_min", "60"),
    ("post", "/v1/report", "report_ip_rate_per_hour", "3600"),
    ("post", "/v1/preview", "preview_ip_rate_per_hour", "3600"),
    ("post", "/v1/sms", "sms_ip_rate_per_hour", "3600"),
    ("post", "/v1/batch", "batch_rate_per_hour", "3600"),
])
def test_every_public_route_has_an_address_limit(client, settings, live_limits, method, path, setting, window):
    setattr(settings, setting, 0)
    bodies = {"/v1/report": {"url": URL}, "/v1/preview": {"url": URL}, "/v1/sms": {"text": "hello"},
              "/v1/batch": {"urls": [URL]}}
    response = getattr(client, method)(path, **({"json": bodies[path]} if method == "post" else {}))
    assert response.status_code == 429
    assert response.headers["retry-after"] == str(int(window) - 5)


def test_a_wrong_bearer_is_counted_and_then_refused(client, settings, live_limits):
    settings.auth_fail_per_10min = 2
    codes = [client.post("/v1/review/ev_1", json={"decision": "confirm"}, headers=WRONG).status_code for _ in range(3)]
    assert codes == [401, 401, 429]
    assert client.post("/v1/review/ev_1", json={"decision": "confirm"}, headers=TOKEN).status_code == 429
    limited = client.post("/v1/review/ev_1", json={"decision": "confirm"}, headers=WRONG)
    assert limited.headers["retry-after"] == "595"


def test_requests_without_a_token_are_not_counted_as_failures(client, settings, live_limits):
    settings.auth_fail_per_10min = 1
    codes = [client.post("/v1/review/ev_1", json={"decision": "confirm"}).status_code for _ in range(4)]
    assert codes == [401] * 4
    assert live_limits.counts == {}


def test_a_wrong_token_on_the_socket_is_counted_per_address(client, settings, live_limits):
    settings.auth_fail_per_10min = 1

    def refused_code():
        with pytest.raises(WebSocketDisconnect) as refused, client.websocket_connect("/v1/events") as socket:
            socket.send_text(json.dumps({"type": "auth", "token": "nope"}))
            socket.receive_text()
        return refused.value.code

    assert [refused_code(), refused_code()] == [events.UNAUTHORISED, events.TOO_MANY_ATTEMPTS]


# Batch

def test_batch_deep_needs_the_write_token(client, enqueued):
    body = {"urls": [URL]}
    assert client.post("/v1/batch?deep=true", json=body).status_code == 401
    assert client.post("/v1/batch?deep=true", json=body, headers=TOKEN).status_code == 200
    assert client.post("/v1/batch", json=body).status_code == 200


def test_batch_url_cap_defaults_to_5000_and_can_be_lowered(client, settings):
    assert settings.batch_max_urls == 5000
    assert client.post("/v1/batch", json={"urls": ["https://a.example/"] * 5001}).status_code == 422
    settings.batch_max_urls = 2
    assert client.post("/v1/batch", json={"urls": ["https://a.example/"] * 3}).status_code == 422
    assert client.post("/v1/batch", json={"urls": ["https://a.example/"] * 2}).status_code == 200


# Spend caps

class FakeAnthropic:
    def __init__(self):
        self.calls = 0
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(stop_reason="end_turn", model="m", content=[SimpleNamespace(type="text", text='{"a": 1}')])


@pytest.fixture
def ai(monkeypatch):
    fake = FakeAnthropic()
    monkeypatch.setattr(provider, "client", lambda: fake)
    monkeypatch.setattr(cache, "get_json_sync", lambda key: None)
    monkeypatch.setattr(cache, "set_json_sync", lambda key, value, ttl_s: None)
    return fake


def ask(settings, monkeypatch):
    monkeypatch.setattr(provider, "get_settings", lambda: settings)
    return provider.structured("page", "system", [{"type": "text", "text": "x"}], {})


def refuse_redis(monkeypatch):
    def forbidden(name):
        raise AssertionError("an unset cap must not touch its Redis counter")

    monkeypatch.setattr(budget, "key", forbidden)


def test_without_an_ai_cap_calls_go_through_and_redis_is_untouched(ai, monkeypatch):
    refuse_redis(monkeypatch)
    settings = Settings(anthropic_api_key="key", ai_daily_calls=None)
    assert [ask(settings, monkeypatch)["a"] for _ in range(3)] == [1, 1, 1]
    assert ai.calls == 3


def test_with_an_ai_cap_the_call_over_the_limit_is_unavailable(ai, fake_redis, monkeypatch):
    settings = Settings(anthropic_api_key="key", ai_daily_calls=2)
    ask(settings, monkeypatch)
    ask(settings, monkeypatch)
    with pytest.raises(provider.AIUnavailable, match="daily AI limit"):
        ask(settings, monkeypatch)
    assert ai.calls == 2
    assert budget.entry("ai", 2) == {"used": 2, "limit": 2, "reached": True}


def test_a_cap_that_cannot_be_read_counts_as_reached(monkeypatch):
    import redis

    def broken():
        raise redis.ConnectionError("down")

    monkeypatch.setattr(cache, "sync_client", broken)
    assert budget.reserve("deep", 5) is False
    assert budget.entry("deep", 5) == {"used": 0, "limit": 5, "reached": True}


def deep_check(client, host):
    return client.post("/v1/check", json={"url": f"https://{host}/", "source": "browser", "mode": "deep"})


def test_without_a_deep_cap_deep_checks_are_queued_and_redis_is_untouched(client, enqueued, monkeypatch):
    refuse_redis(monkeypatch)
    assert deep_check(client, "bakery-one.example").json()["deep_status"] == "queued"
    assert deep_check(client, "bakery-two.example").json()["deep_status"] == "queued"
    assert len(enqueued) == 2


def test_with_a_deep_cap_the_check_over_the_limit_is_not_queued(client, settings, enqueued, fake_redis):
    settings.deep_daily_checks = 1
    first = deep_check(client, "bakery-one.example").json()
    second = deep_check(client, "bakery-two.example").json()
    assert first["deep_status"] == "queued" and len(enqueued) == 1
    assert second["deep_status"] != "queued"
    assert set(second) == set(first)


def test_a_check_that_joins_a_running_job_spends_nothing(client, settings, enqueued, fake_redis, monkeypatch):
    from app import queue

    settings.deep_daily_checks = 1
    monkeypatch.setattr(queue, "claim_deep", lambda host: False)
    assert deep_check(client, "bakery-one.example").json()["deep_status"] == "joined"
    assert enqueued == [] and budget.entry("deep", 1)["used"] == 0


def test_a_spent_budget_releases_the_host_claim(client, settings, enqueued, fake_redis, monkeypatch):
    from app import queue

    released = []
    monkeypatch.setattr(queue, "release_deep", released.append)
    settings.deep_daily_checks = 0
    assert deep_check(client, "bakery-one.example").json()["deep_status"] is None
    assert enqueued == [] and released == ["bakery-one.example"]


def test_health_reports_the_budget(client, settings, fake_redis):
    unset = client.get("/v1/admin/health", headers=TOKEN).json()["budget"]
    assert unset == {"ai": {"used": 0, "limit": None, "reached": False},
                     "deep": {"used": 0, "limit": None, "reached": False}}
    settings.deep_daily_checks = 1
    settings.ai_daily_calls = 5
    assert budget.reserve("deep", 1)
    capped = client.get("/v1/admin/health", headers=TOKEN).json()["budget"]
    assert capped["deep"] == {"used": 1, "limit": 1, "reached": True}
    assert capped["ai"] == {"used": 0, "limit": 5, "reached": False}


# Static serving

@pytest.fixture
def site(tmp_path):
    for name in ("resident", "console"):
        (tmp_path / name / "assets").mkdir(parents=True)
        (tmp_path / name / "index.html").write_text(f"<html>{name}</html>")
        (tmp_path / name / "assets" / "app.js").write_text("export {}")
    api = FastAPI()
    v1 = APIRouter(prefix="/v1")
    v1.add_api_route("/ping", lambda: {"ok": True})
    api.include_router(v1)
    api.add_api_route("/healthz", lambda: {"status": "ok"})
    static.install(api, str(tmp_path))
    return TestClient(api)


def test_each_app_falls_back_to_its_own_index(site):
    assert site.get("/").text == "<html>resident</html>"
    assert site.get("/report/some/route").text == "<html>resident</html>"
    assert site.get("/console/").text == "<html>console</html>"
    assert site.get("/console/cases/42").text == "<html>console</html>"
    assert site.get("/console").text == "<html>console</html>"


def test_api_paths_never_fall_back(site):
    assert site.get("/v1/ping").json() == {"ok": True}
    assert site.get("/healthz").json() == {"status": "ok"}
    unknown = site.get("/v1/nope")
    assert unknown.status_code == 404 and unknown.json() == {"detail": "Not Found"}
    assert site.get("/assets/missing.js").status_code == 404
    assert site.get("/favicon.svg").status_code == 404
    assert site.get("/console/missing.js").status_code == 404


def test_static_cache_and_security_headers(site):
    index = site.get("/")
    asset = site.get("/assets/app.js")
    assert index.headers["cache-control"] == "no-cache"
    assert "immutable" in asset.headers["cache-control"]
    for response in (index, asset, site.get("/console/cases/42")):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"


# The Android routes keep their shape and need no token

def test_tokenless_android_routes_keep_their_shape(client):
    check = client.post("/v1/check", json={"url": URL, "source": "gatekeeper", "mode": "fast"})
    assert check.status_code == 200 and set(check.json()) == set(Verdict.model_fields)
    fetched = client.get(f"/v1/check/{check.json()['check_id']}?view=resident")
    assert fetched.status_code == 200 and set(fetched.json()) == set(Verdict.model_fields)
    blocklist = client.get("/v1/blocklist")
    assert blocklist.status_code == 200 and set(blocklist.json()) == set(BlocklistResponse.model_fields)
    report = client.post("/v1/report", json={"url": "https://unknown-site.example/"})
    assert report.status_code == 202 and set(report.json()) == set(ReportResponse.model_fields)
