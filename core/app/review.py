"""Officer decisions on a case (docs/admin-dashboard.md, "Review route change").

Confirm puts the site on the blocklist (`confirmed_by = 'officer'`); reject clears it only for "legitimate
site" or "not a scam", and every reject takes a confirmed status off the site. Both stamp the check as an
officer verdict, write a review, a verdict row and an audit row, bump the blocklist version (so cached fast
verdicts are not reused) and publish `case.reviewed` once the commit has gone through.

`auto_confirm` is the deep job's own confirmation (`confirmed_by = 'auto'`); an officer can undo it.
"""
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import event, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import audit, cache
from app.fast import intel
from app.graph import build as graph
from app.models import Check, Domain, Evidence, Review, Verdict
from app.verdict.bands import total
from app.verdict.reasons import reason

REJECT_REASONS = ("legitimate_site", "not_a_scam", "parked_or_empty", "already_offline", "not_enough_evidence",
                  "test_or_internal", "duplicate")
REASON_ALIASES = {"insufficient_evidence": "not_enough_evidence"}
CLEARING = ("legitimate_site", "not_a_scam")
PROTECTED = ("official", "allowlisted")
# What a resident sees in "My reports" for each outcome. The officer's free-text note never leaves the console.
RESIDENT_TEXT = {
    "confirm": ("Confirmed as a scam by the police", "أكّدت الشرطة أن هذا الموقع احتيالي"),
    "legitimate_site": ("Reviewed: looks legitimate", "تمت المراجعة: يبدو موقعًا شرعيًا"),
    "not_a_scam": ("Reviewed: not a scam", "تمت المراجعة: ليس احتيالًا"),
    "not_enough_evidence": ("Reviewed: not enough evidence yet; we keep watching it",
                            "تمت المراجعة: لا توجد أدلة كافية بعد؛ نواصل مراقبته"),
    "parked_or_empty": ("Reviewed: the site is empty or parked", "تمت المراجعة: الموقع فارغ أو غير مفعّل"),
    "already_offline": ("Reviewed: the site is already offline", "تمت المراجعة: الموقع متوقف بالفعل"),
    "test_or_internal": ("Reviewed: a test or internal page", "تمت المراجعة: صفحة اختبار أو داخلية"),
    "duplicate": ("Reviewed: already handled in another case", "تمت المراجعة: عولج في بلاغ آخر"),
}
RESIDENT_TEXT["insufficient_evidence"] = RESIDENT_TEXT["not_enough_evidence"]  # rows stored before the alias
BUMP = "bump_blocklist_version"


class ReviewRefused(Exception):
    pass


@dataclass
class Outcome:
    review: Review
    domain: str
    status: str | None
    check: Check
    blocklist_changed: bool = False


@event.listens_for(Session, "after_commit")
def bump_after_commit(session: Session) -> None:
    if session.info.pop(BUMP, False):
        cache.bump_blocklist_version()


@event.listens_for(Session, "after_soft_rollback")
def drop_bump(session: Session, previous_transaction) -> None:
    session.info.pop(BUMP, None)


def confirmer(row: Domain | None) -> str | None:
    """Who confirmed the site, 'officer' or 'auto'. Rows written before `confirmed_by` existed fall back to `source`."""
    if row is None or row.status != "confirmed":
        return None
    return row.confirmed_by or ("officer" if row.source == "officer" else "auto")


def snapshot(row: Domain | None) -> dict | None:
    if row is None:
        return None
    return {"status": row.status, "confirmed_by": confirmer(row), "brand_id": row.brand_id}


def set_status(session: Session, domain: str, status: str, brand_id: str | None, confirmed_by: str | None = None) -> None:
    """Upsert the decision. `confirmed_by` is 'officer' or 'auto' for a confirmation and None otherwise."""
    now = datetime.now(UTC)
    source = confirmed_by or "officer"
    statement = insert(Domain).values(domain=domain, status=status, brand_id=brand_id, source=source,
                                      confirmed_by=confirmed_by, updated_at=now)
    session.execute(statement.on_conflict_do_update(
        index_elements=[Domain.domain],
        set_={"status": status, "source": source, "confirmed_by": confirmed_by, "updated_at": now,
              "brand_id": statement.excluded.brand_id if brand_id else Domain.brand_id},
    ))


def latest_reject(session: Session, site: str) -> Review | None:
    """The newest review on this site's checks, when it is a reject."""
    latest = session.scalars(
        select(Review).join(Evidence, Evidence.id == Review.evidence_id).join(Check, Check.id == Evidence.check_id)
        .where((Check.domain == site) | (Check.host == site)).order_by(Review.id.desc()).limit(1)
    ).first()
    return latest if latest is not None and latest.decision == "reject" else None


def review(session: Session, evidence_id: str, decision: str, reviewer: str, reason_code: str | None = None,
           note: str = "") -> Outcome:
    """Apply one officer decision. The caller commits, then calls `after_commit`."""
    evidence = session.get(Evidence, evidence_id)
    if evidence is None:
        raise LookupError(evidence_id)
    reason_code = REASON_ALIASES.get(reason_code, reason_code)
    if decision == "reject" and reason_code not in REJECT_REASONS:
        raise ReviewRefused("reject needs a reason: " + ", ".join(REJECT_REASONS))
    check = session.get(Check, evidence.check_id)
    site = intel.site_key(session, check.host or "", check.domain)
    row = session.get(Domain, site)
    before = {"status": row.status if row else None, "verdict": check.verdict, "score": check.score}
    if decision == "confirm" and row is not None and row.status in PROTECTED:
        raise ReviewRefused(f"{site} is {row.status}; it cannot be confirmed as a scam")

    status = None
    changed = False
    officer_reasons = [item for item in check.reasons or [] if item["code"] not in ("OFFICER_CONFIRMED", "OFFICER_CLEARED")]
    protected = row is not None and row.status in PROTECTED
    if decision == "confirm":
        status = "confirmed"
        set_status(session, site, status, check.brand_id, "officer")
        officer_reasons.append(reason("OFFICER_CONFIRMED"))
        check.score, check.verdict = 100, "block"
        changed = True
    elif reason_code in CLEARING and not protected:
        status = "cleared"
        changed = row is not None and row.status == "confirmed"
        set_status(session, site, status, check.brand_id)
        officer_reasons = [reason("OFFICER_CLEARED")]
        check.score, check.verdict = 0, "allow"
    else:
        check.score = total(officer_reasons)
        if row is not None and row.status == "confirmed":  # every reject takes the confirmation off the site
            session.delete(row)
            changed = True
    check.reasons = officer_reasons
    check.stage = "officer"

    entry = Review(evidence_id=evidence_id, decision=decision, reviewer=reviewer, reason=reason_code, note=note or None)
    session.add(entry)
    session.add(Verdict(check_id=check.id, verdict=check.verdict, score=check.score, stage="officer", reasons=check.reasons))
    audit.record(session, reviewer, f"review.{decision}", "domain", site, before,
                 {"status": status or (None if changed else before["status"]), "verdict": check.verdict,
                  "score": check.score, "evidence_id": evidence_id}, reason_code)
    session.flush()
    if status or changed:
        graph.refresh(session, site)
    return Outcome(entry, site, status, check, changed or bool(status))


def auto_confirm(session: Session, site: str, brand_id: str | None, evidence_id: str) -> None:
    """Confirm a site without an officer (the deep job: score above 90 and the page asks for credentials).

    Refuses silently when the site is official, allowlisted, cleared or already confirmed, or when an
    officer rejected it last. The caller commits; the event goes out after that commit.
    """
    row = session.get(Domain, site)
    if row is not None and row.status in (*PROTECTED, "confirmed", "cleared"):
        return
    if latest_reject(session, site) is not None:
        return
    before = snapshot(row)
    set_status(session, site, "confirmed", brand_id, "auto")
    audit.record(session, "system", "case.auto_confirm", "domain", site, before,
                 {"status": "confirmed", "confirmed_by": "auto", "brand_id": brand_id, "evidence_id": evidence_id})
    session.flush()
    session.info[BUMP] = True
    graph.refresh(session, site)
    from app import events

    events.publish_after_commit(session, "case.reviewed", {"domain": site, "decision": "auto_confirm", "reviewer": "system"})


def undo_auto_confirm(session: Session, site: str, reviewer: str, note: str | None = None) -> None:
    """Take an automatic confirmation off the site, so the case is open again. The caller commits."""
    row = session.get(Domain, site)
    if confirmer(row) != "auto":
        raise ReviewRefused("Only an auto-confirmed site can be undone")
    before = snapshot(row)
    session.delete(row)
    audit.record(session, reviewer, "case.undo_auto_confirm", "domain", site, before, None, note)
    session.flush()
    session.info[BUMP] = True
    graph.refresh(session, site)
    from app import events

    events.publish_after_commit(session, "case.reviewed", {"domain": site, "decision": "undo_auto_confirm", "reviewer": reviewer})


def after_commit(outcome: Outcome) -> int | None:
    """Side effects that must only happen once the decision is stored."""
    from app import events

    version = None
    if outcome.blocklist_changed:
        cache.bump_blocklist_version()
        version = cache.blocklist_version()
    events.publish("case.reviewed", {"domain": outcome.domain, "decision": outcome.review.decision,
                                     "reviewer": outcome.review.reviewer})
    return version
