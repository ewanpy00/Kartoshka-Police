"""Officer decisions on a case (docs/admin-dashboard.md, "Review route change").

Confirm puts the site on the blocklist; reject clears it only for "legitimate site" or "not a scam".
Both stamp the check as an officer verdict, write a review, a verdict row and an audit row, bump the
blocklist version (so cached fast verdicts are not reused) and publish `case.reviewed`.
"""
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import audit, cache
from app.fast import intel
from app.graph import build as graph
from app.models import Check, Domain, Evidence, Review, Verdict
from app.verdict.bands import total
from app.verdict.reasons import reason

REJECT_REASONS = ("legitimate_site", "not_a_scam", "insufficient_evidence", "duplicate")
CLEARING = ("legitimate_site", "not_a_scam")
PROTECTED = ("official", "allowlisted")
# What a resident sees in "My reports" for each outcome. The officer's free-text note never leaves the console.
RESIDENT_TEXT = {
    "confirm": ("Confirmed as a scam by the police", "أكّدت الشرطة أن هذا الموقع احتيالي"),
    "legitimate_site": ("Reviewed: looks legitimate", "تمت المراجعة: يبدو موقعًا شرعيًا"),
    "not_a_scam": ("Reviewed: not a scam", "تمت المراجعة: ليس احتيالًا"),
    "insufficient_evidence": ("Reviewed: not enough evidence yet; we keep watching it",
                              "تمت المراجعة: لا توجد أدلة كافية بعد؛ نواصل مراقبته"),
    "duplicate": ("Reviewed: already handled in another case", "تمت المراجعة: عولج في بلاغ آخر"),
}


class ReviewRefused(Exception):
    pass


@dataclass
class Outcome:
    review: Review
    domain: str
    status: str | None
    check: Check


def set_status(session: Session, domain: str, status: str, brand_id: str | None) -> None:
    now = datetime.now(UTC)
    statement = insert(Domain).values(domain=domain, status=status, brand_id=brand_id, source="officer", updated_at=now)
    session.execute(statement.on_conflict_do_update(
        index_elements=[Domain.domain],
        set_={"status": status, "source": "officer", "updated_at": now,
              "brand_id": statement.excluded.brand_id if brand_id else Domain.brand_id},
    ))


def review(session: Session, evidence_id: str, decision: str, reviewer: str, reason_code: str | None = None,
           note: str = "") -> Outcome:
    """Apply one officer decision. The caller commits, then calls `after_commit`."""
    evidence = session.get(Evidence, evidence_id)
    if evidence is None:
        raise LookupError(evidence_id)
    if decision == "reject" and reason_code not in REJECT_REASONS:
        raise ReviewRefused("reject needs a reason: " + ", ".join(REJECT_REASONS))
    check = session.get(Check, evidence.check_id)
    site = intel.site_key(session, check.host or "", check.domain)
    row = session.get(Domain, site)
    before = {"status": row.status if row else None, "verdict": check.verdict, "score": check.score}
    if decision == "confirm" and row is not None and row.status in PROTECTED:
        raise ReviewRefused(f"{site} is {row.status}; it cannot be confirmed as a scam")

    status = None
    officer_reasons = [item for item in check.reasons or [] if item["code"] not in ("OFFICER_CONFIRMED", "OFFICER_CLEARED")]
    if decision == "confirm":
        status = "confirmed"
        set_status(session, site, status, check.brand_id)
        officer_reasons.append(reason("OFFICER_CONFIRMED"))
        check.score, check.verdict = 100, "block"
    elif reason_code in CLEARING:
        status = "cleared"
        set_status(session, site, status, check.brand_id)
        officer_reasons = [reason("OFFICER_CLEARED")]
        check.score, check.verdict = 0, "allow"
    else:
        check.score = total(officer_reasons)
    check.reasons = officer_reasons
    check.stage = "officer"

    entry = Review(evidence_id=evidence_id, decision=decision, reviewer=reviewer, reason=reason_code, note=note or None)
    session.add(entry)
    session.add(Verdict(check_id=check.id, verdict=check.verdict, score=check.score, stage="officer", reasons=check.reasons))
    audit.record(session, reviewer, f"review.{decision}", "domain", site, before,
                 {"status": status or before["status"], "verdict": check.verdict, "score": check.score,
                  "evidence_id": evidence_id}, reason_code)
    session.flush()
    if status:
        graph.refresh(session, site)
    return Outcome(entry, site, status, check)


def after_commit(outcome: Outcome) -> int | None:
    """Side effects that must only happen once the decision is stored."""
    version = None
    if outcome.status:
        cache.bump_blocklist_version()
        version = cache.blocklist_version()
    cache.publish({"type": "case.reviewed", "domain": outcome.domain, "decision": outcome.review.decision,
                   "reviewer": outcome.review.reviewer, "at": datetime.now(UTC).isoformat()})
    return version
