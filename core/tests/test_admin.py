"""Officer console (D1) and the review route: auth, queue ranking, decisions, audit log."""
from datetime import timedelta

import pytest
from factories import NOW, make_check, with_evidence
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app import audit, cache
from app.admin import queue as cases
from app.main import app
from app.models import AuditLog, Domain, FeedEntry, Hit, Report, Review, Verdict

AUTH = {"Authorization": "Bearer test-token"}


def admin_routes():
    for path, operations in app.openapi()["paths"].items():
        if path.startswith("/v1/admin"):
            for method in operations:
                yield method.upper(), path


def test_every_admin_route_needs_the_token(client):
    routes = list(admin_routes())
    assert len(routes) >= 8
    for method, path in routes:
        url = path.replace("{domain}", "example.test")
        assert client.request(method, url, json={}).status_code == 401, (method, path)
        assert client.request(method, url, json={}, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_events_socket_closes_with_4401_without_the_right_first_message(client):
    from starlette.websockets import WebSocketDisconnect

    for first in ({"type": "auth", "token": "nope"}, {"type": "auth"}, {"type": "hello", "token": "test-token"}):
        with client.websocket_connect("/v1/events") as socket:
            socket.send_json(first)
            with pytest.raises(WebSocketDisconnect) as closed:
                socket.receive_json()
        assert closed.value.code == 4401


def test_events_socket_ignores_a_token_in_the_url(client):
    from starlette.websockets import WebSocketDisconnect

    with client.websocket_connect("/v1/events?token=test-token") as socket:
        socket.send_json({"type": "auth", "token": "nope"})
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
    assert closed.value.code == 4401


def test_queue_ranks_by_priority(session):
    # Reports and hits multiply, freshness halves every day, and the 30-70 band gets a 1.3 boost.
    make_check(session, "rank-a.test", 90, hours_ago=1)
    make_check(session, "rank-b.test", 50, hours_ago=1)
    make_check(session, "rank-c.test", 90, hours_ago=48)
    make_check(session, "rank-d.test", 90, hours_ago=1)
    for site in ("rank-a.test", "rank-b.test", "rank-c.test"):
        session.add(Hit(domain=site, channel="dns", count=3))
    session.flush()
    order = [c.site for c in cases.ranked(session, NOW) if c.site.startswith("rank-")]
    # a: 90 x ln4 x ~0.97; b: 50 x ln4 x ~0.97 x 1.3; c: 90 x ln4 x 0.25; d has no reports or hits (priority 0)
    assert order == ["rank-a.test", "rank-b.test", "rank-c.test", "rank-d.test"]
    a = next(c for c in cases.ranked(session, NOW) if c.site == "rank-a.test")
    assert a.hits == 3 and a.priority(NOW) > 0


def test_queue_leaves_out_decided_sites_and_shows_auto_confirmed(session):
    for site, status, source in [("q-official.test", "official", "seed"), ("q-allowed.test", "allowlisted", "seed"),
                                 ("q-cleared.test", "cleared", "officer"), ("q-confirmed.test", "confirmed", "officer"),
                                 ("q-auto.test", "confirmed", "auto")]:
        make_check(session, site, 80)
        session.add(Domain(domain=site, status=status, source=source, confirmed_by=source if status == "confirmed" else None))
    make_check(session, "q-open.test", 80)
    session.flush()
    sites = {c.site for c in cases.ranked(session, NOW)}
    assert "q-open.test" in sites
    assert not sites & {"q-official.test", "q-allowed.test", "q-cleared.test", "q-confirmed.test", "q-auto.test"}
    auto = {c.site for c in cases.ranked(session, NOW, auto=True)}
    assert "q-auto.test" in auto and "q-confirmed.test" not in auto and "q-open.test" not in auto


def test_queue_includes_reports_and_feed_entries(session):
    check = make_check(session, "q-report.test", 10)
    session.add(Report(id="r_test1", token_hash="x" * 64, check_id=check.id, url=check.url, domain="q-report.test"))
    session.add(FeedEntry(source="ct", url="https://q-feed.test/", domain="q-feed.test", brand_id="tamm"))
    session.flush()
    found = {c.site: c for c in cases.ranked(session, NOW)}
    assert found["q-report.test"].reports == 1 and "user_report" in found["q-report.test"].sources
    assert found["q-feed.test"].feeds == {"ct"}
    assert {c.site for c in cases.ranked(session, NOW, source="ct")} >= {"q-feed.test"}
    assert "q-report.test" in {c.site for c in cases.ranked(session, NOW, has_reports=True)}


def test_queue_and_case_routes(client, session):
    check = make_check(session, "q-route.test", 85)
    with_evidence(session, check)
    session.add(Hit(domain="q-route.test", channel="dns", count=2))
    session.flush()
    body = client.get("/v1/admin/queue", headers=AUTH).json()
    row = next(item for item in body["cases"] if item["domain"] == "q-route.test")
    assert row["display"] == "q-route[.]test" and row["hits"] == 2 and row["evidence_id"] == check.evidence_id
    assert row["top_reasons"][0]["weight"] > 0
    card = client.get("/v1/admin/cases/q-route.test", headers=AUTH).json()
    assert card["latest"]["display_url"] == "hxxps://q-route[.]test/pay"
    assert card["hits"] == {"dns": 2}
    assert client.get("/v1/admin/cases/nothing-here.test", headers=AUTH).status_code == 404


def test_confirm_blocks_the_site_and_writes_the_trail(client, session, monkeypatch):
    bumps = []
    monkeypatch.setattr(cache, "bump_blocklist_version", lambda: bumps.append(1))  # conftest stubs it out
    check = make_check(session, "confirm-me.test", 80)
    evidence_id = with_evidence(session, check)
    response = client.post(f"/v1/review/{evidence_id}", headers=AUTH, json={"decision": "confirm", "reviewer": "Officer A"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "confirmed" and body["domain"] == "confirm-me.test"
    assert bumps == [1]
    row = session.get(Domain, "confirm-me.test")
    assert row.status == "confirmed" and row.source == "officer" and row.confirmed_by == "officer"
    session.refresh(check)
    assert check.verdict == "block" and check.stage == "officer"
    assert session.scalar(select(Verdict).where(Verdict.check_id == check.id, Verdict.stage == "officer")) is not None
    trail = session.scalar(select(AuditLog).where(AuditLog.target == "confirm-me.test"))
    assert trail.action == "review.confirm" and trail.actor == "Officer A" and trail.after["status"] == "confirmed"
    feed = client.get("/v1/blocklist", params={"since": (NOW - timedelta(minutes=5)).isoformat()}).json()
    assert "confirm-me.test" in [item["domain"] for item in feed["domains"]]


def test_reject_needs_a_reason(client, session):
    evidence_id = with_evidence(session, make_check(session, "reject-me.test", 60))
    assert client.post(f"/v1/review/{evidence_id}", headers=AUTH, json={"decision": "reject"}).status_code == 422
    assert session.scalar(select(Review).where(Review.evidence_id == evidence_id)) is None


def test_reject_clears_only_for_a_legitimate_site(client, session):
    keep = with_evidence(session, make_check(session, "unsure.test", 60))
    body = client.post(f"/v1/review/{keep}", headers=AUTH, json={"decision": "reject", "reason": "insufficient_evidence"}).json()
    assert body["status"] is None and session.get(Domain, "unsure.test") is None
    assert session.scalar(select(Review).where(Review.evidence_id == keep)).reason == "not_enough_evidence"
    clear = with_evidence(session, make_check(session, "fine-shop.test", 60))
    body = client.post(f"/v1/review/{clear}", headers=AUTH, json={"decision": "reject", "reason": "legitimate_site",
                                                                  "note": "their own shop"}).json()
    assert body["status"] == "cleared" and session.get(Domain, "fine-shop.test").status == "cleared"
    stored = session.scalar(select(Review).where(Review.evidence_id == clear))
    assert stored.reason == "legitimate_site" and stored.note == "their own shop"


def test_confirm_refuses_an_allowlisted_site(client, session):
    evidence_id = with_evidence(session, make_check(session, "partner.test", 80))
    session.add(Domain(domain="partner.test", status="allowlisted", source="seed"))
    session.flush()
    response = client.post(f"/v1/review/{evidence_id}", headers=AUTH, json={"decision": "confirm"})
    assert response.status_code == 409
    assert session.get(Domain, "partner.test").status == "allowlisted"


def test_confirm_on_a_shared_platform_blocks_only_that_site(client, session):
    check = make_check(session, "github.io", 80, host="fake-tamm.github.io")
    evidence_id = with_evidence(session, check)
    body = client.post(f"/v1/review/{evidence_id}", headers=AUTH, json={"decision": "confirm"}).json()
    assert body["domain"] == "fake-tamm.github.io"
    assert session.get(Domain, "github.io") is None or session.get(Domain, "github.io").status != "confirmed"


def test_audit_log_is_append_only(session):
    audit.record(session, "tester", "test.action", "domain", "audit.test", {"a": 1}, {"a": 2}, "because")
    session.flush()
    for statement in ("UPDATE audit_log SET actor = 'x' WHERE target = 'audit.test'",
                      "DELETE FROM audit_log WHERE target = 'audit.test'"):
        nested = session.begin_nested()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text(statement))
        nested.rollback()


def test_watch_and_recheck(client, session, enqueued):
    make_check(session, "watch-me.test", 55)
    body = client.post("/v1/admin/cases/watch-me.test/watch", headers=AUTH, json={"reviewer": "Officer B"}).json()
    assert body["display"] == "watch-me[.]test"
    domains, cursor = [], 0
    while cursor is not None:  # the live database may hold more than one page of watched sites
        listed = client.get("/v1/admin/watchlist", headers=AUTH, params={"cursor": cursor}).json()
        domains += [entry["domain"] for entry in listed["entries"]]
        cursor = listed["next_cursor"]
    assert "watch-me.test" in domains
    response = client.post("/v1/admin/cases/watch-me.test/recheck", headers=AUTH, json={})
    assert response.status_code == 200 and response.json()["check_id"] in enqueued


def test_hunter_intake_and_feed(client, session, monkeypatch):
    published = []
    monkeypatch.setattr(cache, "publish", published.append)
    entries = [{"source": "ct", "url": "https://tamm-fines-pay-kptest.xyz/", "brand_id": "tamm"},
               {"source": "ct", "url": "not a url at all"}]
    body = client.post("/v1/intel/feeds", headers=AUTH, json={"entries": entries}).json()
    assert body == {"received": 2, "new": 1, "checked": []}
    assert published[0]["type"] == "hunter.candidate" and published[0]["domain"] == "tamm-fines-pay-kptest.xyz"
    again = client.post("/v1/intel/feeds", headers=AUTH, json={"entries": entries[:1]}).json()
    assert again["new"] == 0
    feed = client.get("/v1/admin/hunter/feed", headers=AUTH, params={"source": "ct", "brand": "tamm"}).json()
    assert feed["entries"][0]["display"] == "tamm-fines-pay-kptest[.]xyz"
    assert client.post("/v1/intel/feeds", json={"entries": []}).status_code == 401


def test_hits_are_counted(client, session):
    client.post("/v1/hits", headers=AUTH, json={"channel": "dns", "counts": {"hits-a.test": 4}})
    client.post("/v1/hits", headers=AUTH, json={"channel": "dns", "counts": {"hits-a.test": 1}})
    assert session.scalar(select(Hit.count).where(Hit.domain == "hits-a.test", Hit.channel == "dns")) == 5


def test_verify_chain_route(client):
    body = client.get("/v1/admin/evidence/verify", headers=AUTH).json()
    assert body["intact"] is True and body["count"] >= 0 and body["first_broken"] is None
    assert body["message"] == "chain intact"


def test_health_route(client):
    body = client.get("/v1/admin/health", headers=AUTH).json()
    assert body["redis"] == "ok" and "url_model" in body["models"]


def test_batch_checks_stay_out_of_the_queue(session):
    make_check(session, "q-batch.test", 90, source="batch")
    session.flush()
    assert "q-batch.test" not in {c.site for c in cases.ranked(session, NOW)}
    assert "q-batch.test" in {c.site for c in cases.ranked(session, NOW, source="batch")}


def test_screen_mode_queues_deep_only_for_suspicious_entries(client, session, enqueued):
    entries = [{"source": "ct", "url": "https://uae-pass-verify-login.top/", "brand_id": "uaepass"},
               {"source": "ct", "url": "https://bakery-recipes-blog.com/"}]
    body = client.post("/v1/intel/feeds", headers=AUTH, json={"entries": entries, "check": True, "check_mode": "screen"}).json()
    verdicts = {item["url"]: item for item in body["checked"]}
    assert verdicts["https://uae-pass-verify-login.top/"]["score"] >= 30
    assert verdicts["https://bakery-recipes-blog.com/"]["score"] < 30
    assert len(enqueued) == 1  # only the suspicious one goes to the sandbox
