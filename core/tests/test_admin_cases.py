"""The case queue and card: officer-only clearing, states, the filters (ported from main's test_admin_cases)."""
from datetime import UTC, datetime, timedelta

from admin_factories import AUTH, add_check, add_evidence, add_report
from app.models import AuditLog, Check, Domain, Watchlist


def queue(client, **params):
    response = client.get("/v1/admin/queue", params=params, headers=AUTH)
    assert response.status_code == 200
    return response.json()["cases"]


def mine(cases, *suffix):
    return [c["domain"] for c in cases if c["domain"].endswith(".example")]


def test_one_case_per_domain_with_several_checks_and_reports(client, session):
    add_check(session, "scam-one.example", 60, source="hunter")
    latest = add_check(session, "scam-one.example", 85, source="api")
    evidence = add_evidence(session, latest)
    for note in ("a", "b"):
        add_report(session, latest, note)
    cases = [c for c in queue(client) if c["domain"] == "scam-one.example"]
    assert len(cases) == 1
    case = cases[0]
    assert (case["checks"], case["reports"], case["score"], case["evidence_id"]) == (2, 2, 85, evidence.id)
    assert case["sources"] == ["api", "hunter", "user_report"]
    assert case["state"] == "open"


def test_queue_filters_by_band_source_and_brand(client, session):
    add_check(session, "blocked.example", 90, source="hunter", brand="TAMM")
    add_check(session, "warned.example", 40, source="api")
    assert mine(queue(client, band="warn")) == ["warned.example"]
    assert mine(queue(client, band="block")) == ["blocked.example"]
    assert mine(queue(client, source="hunter")) == ["blocked.example"]
    assert mine(queue(client, brand="tamm")) == ["blocked.example"]


def test_queue_skips_allow_checks_official_and_allowlisted_domains(client, session):
    add_check(session, "harmless.example", 5)
    add_check(session, "google.com", 80)
    add_report(session, add_check(session, "uaepass.ae", 0), "x")
    assert not {"harmless.example", "google.com", "uaepass.ae"} & {c["domain"] for c in queue(client, state="all")}


def test_cleared_sites_never_appear(client, session):
    add_check(session, "cleared.example", 80)
    session.add(Domain(domain="cleared.example", status="cleared", source="officer"))
    session.flush()
    assert "cleared.example" not in {c["domain"] for c in queue(client, state="all")}


def flagged_then(session, domain, source, score):
    """Block evidence two days ago, then a newer evidence-bearing check from `source`."""
    now = datetime.now(UTC)
    add_evidence(session, add_check(session, domain, 85, created_at=now - timedelta(days=2)))
    add_evidence(session, add_check(session, domain, score, source=source, created_at=now))


def test_an_anonymous_clean_check_cannot_clear_a_case(client, session):
    flagged_then(session, "cloaked.example", "api", 5)
    assert [(c["domain"], c["score"]) for c in queue(client) if c["domain"] == "cloaked.example"] == [("cloaked.example", 85)]


def test_a_resident_or_gatekeeper_clean_check_without_evidence_cannot_clear_a_case(client, session):
    add_evidence(session, add_check(session, "quiet.example", 85, created_at=datetime.now(UTC) - timedelta(days=1)))
    add_check(session, "quiet.example", 0, source="gatekeeper")
    assert [(c["domain"], c["score"]) for c in queue(client) if c["domain"] == "quiet.example"] == [("quiet.example", 85)]


def test_the_representative_is_the_highest_scoring_evidence(client, session):
    now = datetime.now(UTC)
    add_evidence(session, add_check(session, "best.example", 60, created_at=now - timedelta(days=2)))
    top = add_evidence(session, add_check(session, "best.example", 92, created_at=now - timedelta(days=1)))
    add_evidence(session, add_check(session, "best.example", 75, created_at=now))
    case = next(c for c in queue(client) if c["domain"] == "best.example")
    assert (case["score"], case["evidence_id"]) == (92, top.id)


def test_an_officer_recheck_that_scores_allow_clears_the_case(client, session):
    flagged_then(session, "clearing.example", "officer", 5)
    assert "clearing.example" not in {c["domain"] for c in queue(client, state="all")}
    detail = client.get("/v1/admin/cases/clearing.example", headers=AUTH)
    assert (detail.status_code, detail.json()["state"], detail.json()["latest"]["score"]) == (200, "open", 5)


def test_an_anonymous_check_after_an_officer_clear_does_not_reopen_a_clean_case(client, session):
    flagged_then(session, "stays-clear.example", "officer", 5)
    add_evidence(session, add_check(session, "stays-clear.example", 5, source="api"))
    assert "stays-clear.example" not in {c["domain"] for c in queue(client, state="all")}


def test_an_officer_recheck_with_a_report_keeps_the_case(client, session):
    flagged_then(session, "reported-clear.example", "officer", 5)
    add_report(session, add_check(session, "reported-clear.example", 5, source="api"))
    assert "reported-clear.example" in {c["domain"] for c in queue(client)}


def test_an_officer_recheck_that_scores_block_keeps_the_case(client, session):
    flagged_then(session, "still-bad.example", "officer", 90)
    assert [(c["domain"], c["score"]) for c in queue(client) if c["domain"] == "still-bad.example"] == [("still-bad.example", 90)]


def test_a_pending_officer_recheck_keeps_the_earlier_evidence(client, session):
    add_evidence(session, add_check(session, "waiting.example", 85, created_at=datetime.now(UTC) - timedelta(days=1)))
    add_check(session, "waiting.example", 0, verdict="pending", source="officer")
    assert [(c["domain"], c["score"]) for c in queue(client) if c["domain"] == "waiting.example"] == [("waiting.example", 85)]


def test_report_alone_makes_a_case(client, session):
    add_report(session, add_check(session, "reported.example", 0, verdict="pending"), "odd sms")
    assert "reported.example" in {c["domain"] for c in queue(client)}


def test_an_officer_reject_is_respected_against_an_old_check(client, session):
    evidence = add_evidence(session, add_check(session, "rejected.example", 85))
    client.post(f"/v1/review/{evidence.id}", json={"decision": "reject", "reason": "insufficient_evidence"}, headers=AUTH)
    assert "rejected.example" not in {c["domain"] for c in queue(client)}
    rows = [c for c in queue(client, state="all") if c["domain"] == "rejected.example"]
    assert [c["state"] for c in rows] == ["rejected"]


def test_case_detail_reads_the_latest_evidence_and_report_notes(client, session):
    check = add_check(session, "detail.example", 85, brand="TAMM")
    add_evidence(session, check, title="Pay your fine")
    report = add_report(session, check, "came by SMS")
    body = client.get("/v1/admin/cases/detail.example", headers=AUTH).json()
    assert body["title"] == "Pay your fine" and body["has_screenshot"] is True
    assert body["url"] == check.url and body["final_url"] == check.final_url
    assert body["infra"]["rdap"]["registrar"] == "Example Registrar"
    assert body["reasons"][0]["code"] == "LOOKALIKE" and {"weight", "source", "en", "ar"} <= set(body["reasons"][0])
    assert body["reports"]["notes"] == [{"id": report.id, "note": "came by SMS", "created_at": report.created_at.isoformat()}]
    assert len(body["history"]) == 1 and body["evidence_id"] == check.evidence_id
    assert body["location"] == {"hosted_in": "NL", "registered_through": "Example Registrar",
                                "network_owner": "Hoster BV", "behind_proxy": False}
    assert body["report_count"] == 1 and body["state"] == "open"
    assert body["lead_time"]["gsb"]["state"] == "not_polled" and body["lead_time"]["vt"]["at_least_hours"] is None
    assert {"first_seen", "last_seen", "rank", "sources", "campaign_id"} <= set(body)


def test_case_detail_lead_time_reads_first_hits_and_clean_polls(client, session):
    first = datetime.now(UTC) - timedelta(hours=50)
    add_check(session, "lead.example", 85, created_at=first)
    session.add(Domain(domain="lead.example", status="allowlisted", source="seed", vt_first_hit_at=first + timedelta(hours=40)))
    session.add(Watchlist(domain="lead.example", next_check_at=first, expires_at=first, gsb_last_clean_at=first + timedelta(hours=30),
                          vt_last_clean_at=first + timedelta(hours=20)))
    session.flush()
    lead = client.get("/v1/admin/cases/lead.example", headers=AUTH).json()["lead_time"]
    assert lead["gsb"] == {"state": "ahead", "at_least_hours": 30}
    assert lead["vt"] == {"state": "hit", "at_least_hours": 20}


def test_case_detail_without_screenshot_and_unknown_domain(client, session):
    add_evidence(session, add_check(session, "noshot.example", 85), screenshot=False)
    assert client.get("/v1/admin/cases/noshot.example", headers=AUTH).json()["has_screenshot"] is False
    assert client.get("/v1/admin/cases/unknown.example", headers=AUTH).status_code == 404


def test_auto_confirmed_filter_and_undo(client, session):
    add_check(session, "auto.example", 95)
    session.add(Domain(domain="auto.example", status="confirmed", source="auto", confirmed_by="auto"))
    session.flush()
    assert "auto.example" not in {c["domain"] for c in queue(client)}
    assert [c["state"] for c in queue(client, state="auto_confirmed") if c["domain"] == "auto.example"] == ["auto_confirmed"]
    response = client.post("/v1/admin/cases/auto.example/undo-auto-confirm", json={"reviewer": "Sara"}, headers=AUTH)
    assert response.json() == {"domain": "auto.example", "state": "open"}
    assert "auto.example" in {c["domain"] for c in queue(client)}
    entry = session.query(AuditLog).filter_by(action="case.undo_auto_confirm", target="auto.example").one()
    assert (entry.actor, entry.before["confirmed_by"]) == ("Sara", "auto")


def test_undo_refuses_an_officer_confirmed_domain(client, session):
    add_check(session, "officer.example", 95)
    session.add(Domain(domain="officer.example", status="confirmed", source="officer", confirmed_by="officer"))
    session.flush()
    assert client.post("/v1/admin/cases/officer.example/undo-auto-confirm", json={}, headers=AUTH).status_code == 409
    assert session.get(Domain, "officer.example").status == "confirmed"


def test_all_shows_every_state(client, session):
    add_check(session, "s-open.example", 80)
    add_check(session, "s-auto.example", 80)
    add_check(session, "s-officer.example", 80)
    session.add(Domain(domain="s-auto.example", status="confirmed", source="auto", confirmed_by="auto"))
    session.add(Domain(domain="s-officer.example", status="confirmed", source="officer", confirmed_by="officer"))
    session.flush()
    states = {c["domain"]: c["state"] for c in queue(client, state="all") if c["domain"].startswith("s-")}
    assert states == {"s-open.example": "open", "s-auto.example": "auto_confirmed", "s-officer.example": "confirmed"}


def test_recheck_queues_a_deep_check_and_audits(client, session, enqueued):
    add_check(session, "again.example", 60)
    response = client.post("/v1/admin/cases/again.example/recheck", json={"reviewer": "Sara"}, headers=AUTH)
    assert response.status_code == 200 and response.json()["check_id"] in enqueued
    assert session.query(AuditLog).filter_by(action="case.recheck", actor="Sara", target="again.example").count() == 1


def test_recheck_reruns_the_flagged_url_not_the_latest_one(client, session, enqueued):
    older = datetime.now(UTC) - timedelta(days=1)
    add_evidence(session, add_check(session, "d.example", 85, created_at=older, path="login"))
    add_check(session, "d.example", 0, verdict="allow", path="robots.txt")
    response = client.post("/v1/admin/cases/d.example/recheck", json={}, headers=AUTH)
    assert session.get(Check, response.json()["check_id"]).url == "https://d.example/login"


def test_watch_upserts_the_watchlist_and_audits(client, session):
    add_check(session, "watched.example", 60)
    for _ in range(2):
        assert client.post("/v1/admin/cases/watched.example/watch", json={"reviewer": "Sara"}, headers=AUTH).status_code == 200
    assert session.get(Watchlist, "watched.example") is not None
    assert session.query(AuditLog).filter_by(action="case.watch", target="watched.example").count() == 2


def test_audit_endpoint_filters_by_target_newest_first_and_bounds_the_limit(client, session):
    add_check(session, "one.example", 60)
    add_check(session, "two.example", 60)
    for domain in ("one.example", "two.example", "one.example"):
        client.post(f"/v1/admin/cases/{domain}/watch", json={}, headers=AUTH)
    entries = client.get("/v1/admin/audit", params={"target": "one.example"}, headers=AUTH).json()["entries"]
    assert [e["target"] for e in entries] == ["one.example"] * 2
    assert entries[0]["id"] > entries[1]["id"]
    assert {"id", "actor", "action", "target", "target_kind", "before", "after", "reason", "created_at"} <= set(entries[0])
    assert len(client.get("/v1/admin/audit", params={"limit": 1}, headers=AUTH).json()["entries"]) == 1
    assert client.get("/v1/admin/audit", params={"limit": 501}, headers=AUTH).status_code == 422
