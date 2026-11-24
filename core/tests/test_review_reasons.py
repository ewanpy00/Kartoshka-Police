import pytest
from admin_factories import AUTH, add_check, add_evidence
from app.models import Review
from app.review import REASON_ALIASES, REJECT_REASONS

EIGHT = [*REJECT_REASONS, *REASON_ALIASES]


def reject(client, session, reason, n=0):
    evidence = add_evidence(session, add_check(session, f"reason-{n}.example", 85, brand="UAE PASS"))
    body = {"decision": "reject", "reviewer": "Sara"}
    if reason is not None:
        body["reason"] = reason
    return evidence, client.post(f"/v1/review/{evidence.id}", json=body, headers=AUTH)


def test_the_accepted_reasons_are_exactly_the_eight():
    assert set(EIGHT) == {"legitimate_site", "not_a_scam", "parked_or_empty", "already_offline",
                          "not_enough_evidence", "test_or_internal", "duplicate", "insufficient_evidence"}


@pytest.mark.parametrize("reason", EIGHT)
def test_every_reject_reason_is_accepted(client, session, reason):
    evidence, response = reject(client, session, reason, EIGHT.index(reason))
    assert response.status_code == 200, response.text


def test_an_unknown_reason_is_a_validation_error(client, session):
    assert reject(client, session, "because")[1].status_code == 422


def test_the_alias_is_stored_as_not_enough_evidence(client, session):
    evidence, response = reject(client, session, "insufficient_evidence", 99)
    assert response.status_code == 200
    assert response.json()["reason"] == "not_enough_evidence"
    assert session.query(Review).filter_by(evidence_id=evidence.id).one().reason == "not_enough_evidence"
