"""Officer decisions and the automatic confirmation (ported from main's test_admin_review)."""
import pytest
from admin_factories import AUTH, add_check, add_evidence
from app import events
from app import review as decisions
from app.models import AuditLog, Domain, Review


@pytest.fixture
def published(monkeypatch):
    sent = []
    monkeypatch.setattr(events, "publish", lambda type, data: sent.append((type, data)))
    return sent


def scam_case(session, domain="uaepass-login.example", brand="UAE PASS"):
    return add_evidence(session, add_check(session, domain, 85, brand=brand))


def decide(client, evidence, **body):
    return client.post(f"/v1/review/{evidence.id}", json={"reviewer": "Sara", **body}, headers=AUTH)


def test_confirm_marks_the_domain_confirmed_by_the_officer_and_audits(client, session, published):
    evidence = scam_case(session)
    assert decide(client, evidence, decision="confirm").status_code == 200
    row = session.get(Domain, "uaepass-login.example")
    assert (row.status, row.confirmed_by, row.source) == ("confirmed", "officer", "officer")
    entry = session.query(AuditLog).filter_by(action="review.confirm", target="uaepass-login.example").one()
    assert (entry.actor, entry.before["status"], entry.after["status"]) == ("Sara", None, "confirmed")
    assert published == [("case.reviewed", {"domain": "uaepass-login.example", "decision": "confirm", "reviewer": "Sara"})]


def test_nothing_is_published_before_the_commit(session, published):
    outcome = decisions.review(session, scam_case(session).id, "confirm", "Sara")
    session.flush()
    assert published == []
    decisions.after_commit(outcome)
    assert [event[0] for event in published] == ["case.reviewed"]


@pytest.mark.parametrize("reason", ["parked_or_empty", "already_offline", "not_enough_evidence", "test_or_internal", "duplicate"])
def test_a_non_clearing_reject_takes_off_a_confirmation_and_does_not_clear(session, reason):
    evidence = scam_case(session, domain=f"{reason.replace('_', '-')}.example")
    decisions.review(session, evidence.id, "confirm", "Sara")
    outcome = decisions.review(session, evidence.id, "reject", "Sara", reason)
    assert outcome.status is None and session.get(Domain, outcome.domain) is None
    assert session.query(Review).filter_by(evidence_id=evidence.id, decision="reject").one().reason == reason


@pytest.mark.parametrize("reason", ["legitimate_site", "not_a_scam"])
def test_only_legitimate_site_and_not_a_scam_clear(session, reason):
    evidence = scam_case(session, domain=f"clear-{reason.replace('_', '-')}.example")
    decisions.review(session, evidence.id, "confirm", "Sara")
    outcome = decisions.review(session, evidence.id, "reject", "Sara", reason)
    assert outcome.status == "cleared" and session.get(Domain, outcome.domain).status == "cleared"
    assert session.get(Domain, outcome.domain).confirmed_by is None


def test_insufficient_evidence_is_stored_as_not_enough_evidence(session):
    evidence = scam_case(session)
    decisions.review(session, evidence.id, "reject", "Sara", "insufficient_evidence")
    assert session.query(Review).filter_by(evidence_id=evidence.id).one().reason == "not_enough_evidence"


def test_reject_without_a_valid_reason_is_refused(client, session):
    evidence = scam_case(session)
    assert decide(client, evidence, decision="reject").status_code == 422
    with pytest.raises(decisions.ReviewRefused):
        decisions.review(session, evidence.id, "reject", "Sara", "because")
    assert session.query(Review).filter_by(evidence_id=evidence.id).count() == 0


def test_confirming_an_allowlisted_domain_is_409(client, session):
    evidence = add_evidence(session, add_check(session, "google.com", 85))
    assert decide(client, evidence, decision="confirm").status_code == 409
    assert session.get(Domain, "google.com").status == "allowlisted"


def test_review_of_an_unknown_evidence_id_is_404(client):
    assert client.post("/v1/review/e_missing", json={"decision": "confirm"}, headers=AUTH).status_code == 404


def test_auto_confirm_confirms_a_fresh_domain_audits_and_publishes_after_commit(session, published):
    evidence = scam_case(session)
    decisions.auto_confirm(session, "uaepass-login.example", "uaepass", evidence.id)
    row = session.get(Domain, "uaepass-login.example")
    assert (row.status, row.confirmed_by, row.brand_id) == ("confirmed", "auto", "uaepass")
    entry = session.query(AuditLog).filter_by(action="case.auto_confirm", target="uaepass-login.example").one()
    assert (entry.actor, entry.after["evidence_id"]) == ("system", evidence.id)
    assert published == []  # held until the commit
    assert session.info[events.PENDING] == [
        ("case.reviewed", {"domain": "uaepass-login.example", "decision": "auto_confirm", "reviewer": "system"})]
    session.rollback()
    session.info.pop(events.PENDING, None)


def test_auto_confirm_refuses_official_and_allowlisted_sites_silently(session):
    evidence = scam_case(session, domain="partner.example")
    for site, status in (("partner.example", "allowlisted"), ("official.example", "official")):
        session.add(Domain(domain=site, status=status, source="seed"))
        session.flush()
        decisions.auto_confirm(session, site, "uaepass", evidence.id)
        assert session.get(Domain, site).status == status
    assert session.query(AuditLog).filter_by(action="case.auto_confirm").count() == 0
    assert session.info.get(events.PENDING) is None


def test_auto_confirm_respects_an_earlier_officer_reject_and_an_officer_confirmation(client, session):
    rejected = scam_case(session)
    decide(client, rejected, decision="reject", reason="insufficient_evidence")
    decisions.auto_confirm(session, "uaepass-login.example", "uaepass", rejected.id)
    assert session.get(Domain, "uaepass-login.example") is None
    confirmed = scam_case(session, domain="officer-first.example")
    decisions.review(session, confirmed.id, "confirm", "Sara")
    decisions.auto_confirm(session, "officer-first.example", "uaepass", confirmed.id)
    assert session.get(Domain, "officer-first.example").confirmed_by == "officer"
    assert session.query(AuditLog).filter_by(action="case.auto_confirm").count() == 0
