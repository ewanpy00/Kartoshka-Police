from datetime import UTC, datetime, timedelta

from admin_factories import AUTH, add_check, add_evidence
from app.admin.cases import rank_case
from app.models import AuditLog, Domain, Report, Watchlist

NOW = datetime(2026, 1, 10, tzinfo=UTC)


def queue(client, **params):
    response = client.get("/v1/admin/queue", params=params, headers=AUTH)
    assert response.status_code == 200
    return response.json()["cases"]


def test_rank_case_scales_with_volume_and_decays_with_age():
    fresh = rank_case(80, 1, 1, NOW, NOW)
    assert fresh > rank_case(80, 0, 1, NOW, NOW)
    assert rank_case(80, 1, 1, NOW - timedelta(days=1), NOW) == fresh / 2


def test_rank_case_boosts_only_the_warn_band():
    assert rank_case(69, 0, 1, NOW, NOW) == 1.5 * 69 * rank_case(1, 0, 1, NOW, NOW)
    assert rank_case(70, 0, 1, NOW, NOW) == 70 * rank_case(1, 0, 1, NOW, NOW)
    assert rank_case(30, 0, 1, NOW, NOW) == 1.5 * 30 * rank_case(1, 0, 1, NOW, NOW)
    assert rank_case(29, 0, 1, NOW, NOW) == 29 * rank_case(1, 0, 1, NOW, NOW)


def test_one_case_per_domain_with_several_checks_and_reports(client, session):
    add_check(session, "scam-one.example", 60, source="hunter")
    latest = add_check(session, "scam-one.example", 85, source="api")
    evidence = add_evidence(session, latest)
    session.add_all(Report(domain="scam-one.example", url="https://scam-one.example/", note=n) for n in ("a", "b"))
    session.flush()
    cases = queue(client)
    assert [c["domain"] for c in cases] == ["scam-one.example"]
    case = cases[0]
    assert (case["hits"], case["reports"], case["score"], case["evidence_id"]) == (2, 2, 85, evidence.id)
    assert case["sources"] == ["api", "hunter", "user_report"]
    assert case["state"] == "open"


def test_queue_ranks_the_boosted_warn_case_above_a_plain_block(client, session):
    add_check(session, "plain-block.example", 80)
    add_check(session, "mid-warn.example", 50)
    add_check(session, "mid-warn.example", 50)
    assert [c["domain"] for c in queue(client)] == ["mid-warn.example", "plain-block.example"]


def test_queue_filters_by_band_source_and_brand(client, session):
    add_check(session, "blocked.example", 90, source="hunter", brand="TAMM")
    add_check(session, "warned.example", 40, source="api")
    assert [c["domain"] for c in queue(client, band="warn")] == ["warned.example"]
    assert [c["domain"] for c in queue(client, band="block")] == ["blocked.example"]
    assert [c["domain"] for c in queue(client, source="hunter")] == ["blocked.example"]
    assert [c["domain"] for c in queue(client, brand="tamm")] == ["blocked.example"]


def test_queue_skips_allow_checks_official_and_allowlisted_domains(client, session):
    add_check(session, "harmless.example", 5)
    add_check(session, "google.com", 80)
    session.add(Report(domain="uaepass.ae", url="https://uaepass.ae/"))
    session.flush()
    assert queue(client, state="all") == []


def test_report_alone_makes_a_case(client, session):
    add_check(session, "reported.example", 0, verdict="pending")
    session.add(Report(domain="reported.example", url="https://reported.example/", note="odd sms"))
    session.flush()
    assert [c["domain"] for c in queue(client)] == ["reported.example"]


def test_case_detail_reads_the_latest_evidence_and_report_notes(client, session):
    check = add_check(session, "detail.example", 85)
    add_evidence(session, check, title="Pay your fine")
    session.add(Report(domain="detail.example", url="https://detail.example/", note="came by SMS"))
    session.flush()
    body = client.get("/v1/admin/cases/detail.example", headers=AUTH).json()
    assert body["title"] == "Pay your fine"
    assert body["has_screenshot"] is True
    assert body["infrastructure"]["registrar"] == "Example Registrar"
    assert body["reasons"][0]["code"] == "BRAND"
    assert [n["note"] for n in body["report_notes"]] == ["came by SMS"]
    assert len(body["checks"]) == 1


def test_case_detail_without_screenshot_and_unknown_domain(client, session):
    add_evidence(session, add_check(session, "noshot.example", 85), screenshot=False)
    assert client.get("/v1/admin/cases/noshot.example", headers=AUTH).json()["has_screenshot"] is False
    assert client.get("/v1/admin/cases/unknown.example", headers=AUTH).status_code == 404


def test_auto_confirmed_filter_and_undo(client, session):
    add_check(session, "auto.example", 95)
    session.add(Domain(domain="auto.example", status="confirmed", confirmed_by="auto"))
    session.flush()
    assert queue(client) == []
    assert [c["state"] for c in queue(client, state="auto_confirmed")] == ["auto_confirmed"]
    response = client.post("/v1/admin/cases/auto.example/undo-auto-confirm", json={"reviewer": "Sara"}, headers=AUTH)
    assert response.json() == {"domain": "auto.example", "state": "open"}
    assert [c["domain"] for c in queue(client)] == ["auto.example"]
    entry = session.query(AuditLog).filter_by(action="case.undo_auto_confirm").one()
    assert (entry.actor, entry.target, entry.before["confirmed_by"]) == ("Sara", "auto.example", "auto")


def test_undo_refuses_an_officer_confirmed_domain(client, session):
    add_check(session, "officer.example", 95)
    session.add(Domain(domain="officer.example", status="confirmed", confirmed_by="officer"))
    session.flush()
    response = client.post("/v1/admin/cases/officer.example/undo-auto-confirm", json={}, headers=AUTH)
    assert response.status_code == 409


def test_recheck_queues_a_deep_check_and_audits(client, session, enqueued):
    add_check(session, "again.example", 60)
    response = client.post("/v1/admin/cases/again.example/recheck", json={"reviewer": "Sara"}, headers=AUTH)
    assert response.status_code == 202
    assert enqueued == [response.json()["check_id"]]
    assert session.query(AuditLog).filter_by(action="case.recheck", actor="Sara").count() == 1


def test_watch_upserts_the_watchlist_and_audits(client, session):
    add_check(session, "watched.example", 60)
    for _ in range(2):
        response = client.post("/v1/admin/cases/watched.example/watch", json={"reviewer": "Sara"}, headers=AUTH)
        assert response.status_code == 201
    row = session.get(Watchlist, "watched.example")
    assert row.expires_at - row.next_check_at == timedelta(days=14) - timedelta(hours=6)
    assert session.query(AuditLog).filter_by(action="watchlist.add").count() == 2


def test_audit_endpoint_filters_by_target(client, session):
    add_check(session, "one.example", 60)
    add_check(session, "two.example", 60)
    for domain in ("one.example", "two.example"):
        client.post(f"/v1/admin/cases/{domain}/watch", json={}, headers=AUTH)
    entries = client.get("/v1/admin/audit", params={"target": "one.example"}, headers=AUTH).json()["entries"]
    assert [e["target"] for e in entries] == ["one.example"]
