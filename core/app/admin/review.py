from typing import Literal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import events
from app.admin import audit
from app.brands import load_brands
from app.config import get_settings
from app.models import Domain, Evidence, Review

REJECT_REASONS = ("legitimate_site", "parked_or_empty", "already_offline", "not_enough_evidence", "test_or_internal")
PROTECTED = ("official", "allowlisted")


class ProtectedDomain(Exception):
    """The domain is official or allowlisted and can never be confirmed as a scam."""


def snapshot(row: Domain | None) -> dict | None:
    if row is None:
        return None
    return {"status": row.status, "confirmed_by": row.confirmed_by, "brand_id": row.brand_id}


def resolve_brand_id(value: str | None) -> str | None:
    """Map a brand id or display name from an evidence payload to a brand id."""
    if not value:
        return None
    for brand in load_brands(get_settings().data_dir):
        if value == brand["id"] or value.lower() in (name.lower() for name in brand["names"]):
            return brand["id"]
    return None


def mark_confirmed(session: Session, domain: str, brand_id: str | None, confirmed_by: str) -> Domain:
    row = session.get(Domain, domain)
    if row is None:
        row = Domain(domain=domain)
        session.add(row)
    else:
        row.updated_at = func.now()
    row.status, row.brand_id, row.confirmed_by = "confirmed", brand_id, confirmed_by
    return row


def apply_decision(
    session: Session,
    domain: str,
    evidence_id: str,
    decision: Literal["confirm", "reject"],
    reason: str | None,
    reviewer: str,
) -> Review:
    """Record an officer decision and update the blocklist. The caller commits."""
    if decision == "reject" and reason not in REJECT_REASONS:
        raise ValueError(f"A reject needs a reason, one of: {', '.join(REJECT_REASONS)}")
    row = session.get(Domain, domain)
    before = snapshot(row)
    if decision == "confirm":
        if row is not None and row.status in PROTECTED:
            raise ProtectedDomain(f"{domain} is {row.status} and cannot be confirmed")
        evidence = session.get(Evidence, evidence_id)
        brand_id = resolve_brand_id(evidence.payload.get("scam", {}).get("brand"))
        row = mark_confirmed(session, domain, brand_id, "officer")
    elif row is not None and row.status == "confirmed":
        session.delete(row)
        row = None
    review = Review(evidence_id=evidence_id, decision=decision, reviewer=reviewer, domain=domain, reason=reason)
    session.add(review)
    audit.record(session, reviewer, f"case.{decision}", domain, before, snapshot(row), reason)
    session.flush()
    events.publish("case.reviewed", {"domain": domain, "decision": decision, "reviewer": reviewer})
    return review


def auto_confirm(session: Session, domain: str, brand_id: str | None, evidence_id: str) -> None:
    """Confirm a domain without an officer, unless it is protected or already confirmed. The caller commits."""
    row = session.get(Domain, domain)
    if row is not None and row.status in (*PROTECTED, "confirmed"):
        return
    before = snapshot(row)
    after = snapshot(mark_confirmed(session, domain, brand_id, "auto"))
    audit.record(session, "system", "case.auto_confirm", domain, before, {**after, "evidence_id": evidence_id})
