from admin_factories import AUTH, add_check, add_evidence
from app.admin.review import auto_confirm
from app.models import AuditLog, Check, Domain, Report, Review


def decide(client, evidence, **body):
    return client.post(f"/v1/review/{evidence.id}", json={"reviewer": "Sara", **body}, headers=AUTH)


def scam_case(session, domain="uaepass-login.example", brand="UAE PASS"):
    check = add_check(session, domain, 85)
    return add_evidence(session, check, brand=brand)


def blocklisted(client):
    return {entry["domain"]: entry for entry in client.get("/v1/blocklist").json()["domains"]}


def test_confirm_blocks_the_domain_and_audits(client, session, published):
    evidence = scam_case(session)
    assert decide(client, evidence, decision="confirm").status_code == 200
    assert blocklisted(client)["uaepass-login.example"]["brand_id"] == "uaepass"
    row = session.get(Domain, "uaepass-login.example")
    assert (row.status, row.confirmed_by) == ("confirmed", "officer")
    entry = session.query(AuditLog).filter_by(action="case.confirm").one()
    assert (entry.actor, entry.before, entry.after["status"]) == ("Sara", None, "confirmed")
    assert published == [("case.reviewed", {"domain": "uaepass-login.example", "decision": "confirm", "reviewer": "Sara"})]
    check = client.post("/v1/check", json={"url": "https://uaepass-login.example/x"}).json()
    assert (check["verdict"], check["score"]) == ("block", 100)


def test_reject_stores_the_reason_and_removes_the_domain_from_the_blocklist(client, session):
    evidence = scam_case(session)
    decide(client, evidence, decision="confirm")
    response = decide(client, evidence, decision="reject", reason="legitimate_site")
    assert response.status_code == 200
    assert "uaepass-login.example" not in blocklisted(client)
    review = session.query(Review).filter_by(decision="reject").one()
    assert (review.reason, review.domain) == ("legitimate_site", "uaepass-login.example")
    entry = session.query(AuditLog).filter_by(action="case.reject").one()
    assert (entry.before["status"], entry.after, entry.reason) == ("confirmed", None, "legitimate_site")
    cases = client.get("/v1/admin/queue", params={"state": "all"}, headers=AUTH).json()["cases"]
    assert [c["state"] for c in cases] == ["rejected"]


def test_reject_without_a_valid_reason_is_422(client, session):
    evidence = scam_case(session)
    assert decide(client, evidence, decision="reject").status_code == 422
    assert decide(client, evidence, decision="reject", reason="because").status_code == 422
    assert session.query(Review).count() == 0


def test_confirming_an_allowlisted_domain_is_409(client, session):
    evidence = add_evidence(session, add_check(session, "google.com", 85))
    assert decide(client, evidence, decision="confirm").status_code == 409
    assert session.get(Domain, "google.com").status == "allowlisted"


def test_review_of_an_unknown_evidence_id_is_404(client):
    response = client.post("/v1/review/e_missing", json={"decision": "confirm"}, headers=AUTH)
    assert response.status_code == 404


def test_report_stores_a_row_and_queues_a_deep_check(client, session, enqueued):
    response = client.post("/v1/report", json={"url": "https://www.Phish.example/pay", "note": "got an SMS"})
    assert response.status_code == 202
    report = session.query(Report).one()
    assert (report.domain, report.note, report.check_id) == ("phish.example", "got an SMS", response.json()["check_id"])
    assert enqueued == [report.check_id]


def test_hunter_checks_publish_a_candidate_event(client, published):
    body = client.post(
        "/v1/check", json={"url": "https://tamm-pay.example/", "source": "hunter"}, headers=AUTH
    ).json()
    assert published == [
        ("hunter.candidate", {"domain": "tamm-pay.example", "url": "https://tamm-pay.example/", "brand": None, "check_id": body["check_id"]})
    ]


def test_reserved_sources_need_the_write_token(client, session, published):
    for source in ("hunter", "watchlist", "user_report"):
        response = client.post("/v1/check", json={"url": "https://forged.example/", "source": source})
        assert response.status_code == 401
    assert published == []
    assert session.query(Check).filter_by(domain="forged.example").count() == 0


def test_anonymous_check_with_an_ordinary_source_still_works(client, published):
    response = client.post("/v1/check", json={"url": "https://other.example/", "source": "gatekeeper"})
    assert response.status_code == 200
    assert published == []


def test_auto_confirm_respects_an_earlier_officer_reject(client, session):
    evidence = scam_case(session)
    decide(client, evidence, decision="reject", reason="legitimate_site")
    auto_confirm(session, "uaepass-login.example", "uaepass", evidence.id)
    assert session.get(Domain, "uaepass-login.example") is None
    assert session.query(AuditLog).filter_by(action="case.auto_confirm").count() == 0


def test_auto_confirm_confirms_a_fresh_domain(session):
    evidence = scam_case(session)
    auto_confirm(session, "uaepass-login.example", "uaepass", evidence.id)
    assert session.get(Domain, "uaepass-login.example").confirmed_by == "auto"


def test_report_and_check_inputs_are_length_limited(client):
    long_url = "https://a.example/" + "x" * 2000
    assert client.post("/v1/report", json={"url": long_url}).status_code == 422
    assert client.post("/v1/report", json={"url": "https://a.example/", "note": "n" * 1001}).status_code == 422
    assert client.post("/v1/check", json={"url": long_url}).status_code == 422
