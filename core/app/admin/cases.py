from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import log
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import queue
from app.admin import audit
from app.admin.review import PROTECTED
from app.checks import run_check
from app.config import get_settings
from app.db import get_session
from app.infra import location
from app.models import AuditLog, Check, Domain, Evidence, Report, Review, Watchlist
from app.schemas import (
    AuditResponse,
    CaseDetail,
    CaseSummary,
    OfficerAction,
    QueueResponse,
    RecheckResponse,
    UndoResponse,
    WatchResponse,
)
from app.watch import lead_time

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]
WATCH_INTERVAL = timedelta(hours=6)
WATCH_LIFETIME = timedelta(days=14)


@dataclass
class Case:
    domain: str
    checks: list[Check]
    reports: list[Report]
    reviews: list[Review]
    row: Domain | None
    check: Check
    evidence: Evidence | None

    @property
    def in_queue(self) -> bool:
        return bool(self.reports) or self.check.verdict in ("warn", "block")


def rank_case(score: int, reports: int, hits: int, last_seen: datetime, now: datetime) -> float:
    """Score, weighted by volume and freshness, with a boost for the undecided middle band."""
    days = max((now - last_seen).total_seconds() / 86400, 0)
    boost = 1.5 if 30 <= score < 70 else 1
    return score * log(1 + reports + hits) / (1 + days) * boost


def band_of(score: int) -> str:
    return "block" if score >= 70 else "warn" if score >= 30 else "allow"


def state_of(row: Domain | None, latest_review: Review | None) -> str:
    if row is not None and row.status == "confirmed":
        return "auto_confirmed" if row.confirmed_by == "auto" else "confirmed"
    if latest_review is not None and latest_review.decision == "reject":
        return "rejected"
    return "open"


def group(rows, key) -> defaultdict:
    grouped = defaultdict(list)
    for row in rows:
        grouped[key(row)].append(row)
    return grouped


def pick_representative(checks: list[Check], evidence: dict[str, Evidence]) -> tuple[Check, Evidence | None]:
    """The highest-scoring evidence-bearing check from the latest officer re-run on (all of them if none).

    Only an officer's own re-run can clear a case, so an anonymous clean check cannot hide a scam.
    A recheck still waiting for its evidence leaves the earlier evidence in place.
    Without any evidence the latest check stands in. `checks` is newest first.
    """
    with_evidence = [c for c in checks if c.id in evidence]
    officer_runs = [c.created_at for c in checks if c.source == "officer"]
    since = max(officer_runs, default=None)
    pool = [c for c in with_evidence if since is None or c.created_at >= since] or with_evidence
    if not pool:
        return checks[0], None
    best = max(reversed(pool), key=lambda c: c.score)
    return best, evidence[best.id]


def collect(session: Session, only: str | None = None) -> list[Case]:
    """Every domain with a warn or block check or a report, minus official and allowlisted ones.

    With `only`, any domain that has a check or a report. Callers decide queue membership with `in_queue`.
    """
    if only is None:
        candidates = set(session.scalars(select(Check.domain).where(Check.verdict.in_(("warn", "block")))))
        candidates |= set(session.scalars(select(Report.domain)))
    else:
        candidates = set(session.scalars(select(Check.domain).where(Check.domain == only)))
        candidates |= set(session.scalars(select(Report.domain).where(Report.domain == only)))
    candidates.discard(None)
    rows = {row.domain: row for row in session.scalars(select(Domain).where(Domain.domain.in_(candidates)))}
    candidates = {d for d in candidates if d not in rows or rows[d].status not in PROTECTED}
    checks = group(
        session.scalars(select(Check).where(Check.domain.in_(candidates)).order_by(Check.created_at.desc())),
        lambda check: check.domain,
    )
    reports = group(session.scalars(select(Report).where(Report.domain.in_(candidates))), lambda r: r.domain)
    reviews = group(
        session.scalars(select(Review).where(Review.domain.in_(candidates)).order_by(Review.id.desc())),
        lambda review: review.domain,
    )
    evidence = {
        e.check_id: e
        for e in session.scalars(
            select(Evidence).where(Evidence.check_id.in_([c.id for cs in checks.values() for c in cs])).order_by(Evidence.seq)
        )
    }
    cases = []
    for domain in candidates:
        if not checks[domain]:
            continue
        check, picked = pick_representative(checks[domain], evidence)
        cases.append(Case(domain, checks[domain], reports[domain], reviews[domain], rows.get(domain), check, picked))
    return cases


def summarise(case: Case, now: datetime) -> CaseSummary:
    check = case.check
    seen = [c.created_at for c in case.checks] + [r.created_at for r in case.reports]
    last_seen = max(seen)
    return CaseSummary(
        domain=case.domain,
        state=state_of(case.row, case.reviews[0] if case.reviews else None),
        score=check.score,
        verdict=check.verdict,
        brand=check.brand,
        sources=sorted({c.source for c in case.checks} | ({"user_report"} if case.reports else set())),
        reports=len(case.reports),
        hits=len(case.checks),
        first_seen=min(seen),
        last_seen=last_seen,
        evidence_id=case.evidence.id if case.evidence else None,
        campaign_id=check.campaign_id,
        rank=rank_case(check.score, len(case.reports), len(case.checks), last_seen, now),
    )


def require_case(session: Session, domain: str) -> Case:
    cases = collect(session, domain)
    if not cases:
        raise HTTPException(404, "Unknown case")
    return cases[0]


@router.get("/queue", response_model=QueueResponse)
def queue_view(
    session: SessionDep,
    state: Literal["open", "auto_confirmed", "all"] = "open",
    source: str | None = None,
    brand: str | None = None,
    band: Annotated[Literal["allow", "warn", "block"] | None, Query()] = None,
) -> QueueResponse:
    now = datetime.now(UTC)
    summaries = [summarise(case, now) for case in collect(session) if case.in_queue]
    kept = [
        s for s in summaries
        if state in (s.state, "all")
        and (source is None or source in s.sources)
        and (brand is None or (s.brand or "").lower() == brand.lower())
        and (band is None or band_of(s.score) == band)
    ]
    return QueueResponse(cases=sorted(kept, key=lambda s: s.rank, reverse=True))


@router.get("/cases/{domain}", response_model=CaseDetail)
def case_detail(domain: str, session: SessionDep) -> CaseDetail:
    case = require_case(session, domain)
    check = case.check
    payload = case.evidence.payload if case.evidence else {}
    watching = session.get(Watchlist, domain)
    return CaseDetail(
        **summarise(case, datetime.now(UTC)).model_dump(),
        url=check.url,
        final_url=check.final_url,
        title=payload.get("capture", {}).get("title"),
        reasons=payload.get("risk", {}).get("reasons", check.reasons),
        infrastructure=payload.get("infrastructure", {}),
        location=location(payload["infrastructure"]) if "infrastructure" in payload else None,
        lead_time=lead_time(min(c.created_at for c in case.checks), watching) if watching else None,
        report_notes=[r for r in case.reports if r.note],
        checks=case.checks,
        reviews=case.reviews,
        has_screenshot=bool(payload.get("capture", {}).get("screenshot")),
    )


@router.post("/cases/{domain}/recheck", response_model=RecheckResponse, status_code=202)
def recheck(domain: str, body: OfficerAction, session: SessionDep) -> RecheckResponse:
    case = require_case(session, domain)
    check = run_check(session, case.check.url, "officer", "deep", get_settings().data_dir)
    audit.record(session, body.reviewer, "case.recheck", domain, after={"check_id": check.id})
    session.commit()
    queue.enqueue_deep_check(check.id)
    return RecheckResponse(check_id=check.id)


@router.post("/cases/{domain}/watch", response_model=WatchResponse, status_code=201)
def watch(domain: str, body: OfficerAction, session: SessionDep) -> WatchResponse:
    require_case(session, domain)
    now = datetime.now(UTC)
    entry = session.get(Watchlist, domain) or Watchlist(domain=domain)
    entry.next_check_at, entry.expires_at = now + WATCH_INTERVAL, now + WATCH_LIFETIME
    session.add(entry)
    audit.record(session, body.reviewer, "watchlist.add", domain, after={"expires_at": entry.expires_at.isoformat()})
    session.commit()
    return WatchResponse(domain=domain, next_check_at=entry.next_check_at, expires_at=entry.expires_at)


@router.post("/cases/{domain}/undo-auto-confirm", response_model=UndoResponse)
def undo_auto_confirm(domain: str, body: OfficerAction, session: SessionDep) -> UndoResponse:
    row = session.get(Domain, domain)
    if row is None or row.confirmed_by != "auto":
        raise HTTPException(409, "Only an auto-confirmed domain can be undone")
    before = {"status": row.status, "confirmed_by": row.confirmed_by, "brand_id": row.brand_id}
    session.delete(row)
    audit.record(session, body.reviewer, "case.undo_auto_confirm", domain, before=before)
    session.commit()
    latest = session.scalars(select(Review).where(Review.domain == domain).order_by(Review.id.desc())).first()
    return UndoResponse(domain=domain, state=state_of(None, latest))


@router.get("/audit", response_model=AuditResponse)
def audit_log(session: SessionDep, target: str | None = None, limit: Annotated[int, Query(ge=1, le=500)] = 50) -> AuditResponse:
    query = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if target is not None:
        query = query.where(AuditLog.target == target)
    return AuditResponse(entries=session.scalars(query).all())
