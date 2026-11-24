"""The officer review queue (docs/admin-dashboard.md, "Queue"): one case per site, ranked.

A case is a site (registrable domain, or the full host on a shared platform; docs/app-plan.md decision 14)
with a warn or block check, a resident report or a Hunter feed entry in the last 14 days. Official,
allowlisted and decided sites are left out; auto-confirmed ones (blocklisted without an officer) stay
visible under `auto` until someone reviews them. Checks from the judges' `/v1/batch` route are evaluation
traffic, not sightings: they only show with `source=batch`.

    priority   = score x ln(1 + reports + hits) x freshness x band_boost
    freshness  = 0.5 ^ (hours since the latest sighting / 24)
    band_boost = 1.3 for scores 30-70, else 1.0

The formula is 0 for a case nobody has reported or hit yet, so ties are broken by
score x freshness x band_boost: fresh Hunter finds still sort by how bad and how new they are.
"""
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.defang import defang
from app.fast import intel
from app.models import Campaign, Check, Domain, Evidence, FeedEntry, Hit, Report, Review, Watchlist
from app.verdict.bands import band

WINDOW = timedelta(days=14)
PAGE = 50
DECIDED = ("official", "allowlisted", "confirmed", "cleared")


@dataclass
class Case:
    site: str
    latest: Check | None = None
    last_seen: datetime | None = None
    checks: int = 0
    sources: set[str] = field(default_factory=set)
    reports: int = 0
    hits: int = 0
    feeds: set[str] = field(default_factory=set)
    status: str | None = None
    status_source: str | None = None

    @property
    def score(self) -> int:
        return self.latest.score if self.latest else 0

    def freshness(self, now: datetime) -> float:
        if self.last_seen is None:
            return 0.0
        seen = self.last_seen if self.last_seen.tzinfo else self.last_seen.replace(tzinfo=UTC)
        return 0.5 ** (max(0.0, (now - seen).total_seconds() / 3600) / 24)

    def boost(self) -> float:
        return 1.3 if 30 <= self.score <= 70 else 1.0

    def priority(self, now: datetime) -> float:
        return self.score * math.log(1 + self.reports + self.hits) * self.freshness(now) * self.boost()

    def tiebreak(self, now: datetime) -> float:
        return self.score * self.freshness(now) * self.boost()


def _later(a: datetime | None, b: datetime | None) -> datetime | None:
    if a is None or b is None:
        return a or b
    return max(a, b)


def collect(session: Session, now: datetime, include_batch: bool = False) -> dict[str, Case]:
    since = now - WINDOW
    cases: dict[str, Case] = {}
    query = select(Check).where(Check.created_at >= since, Check.verdict.in_(("warn", "block")))
    if not include_batch:
        query = query.where(Check.source != "batch")
    checks = session.scalars(query.order_by(Check.created_at.desc()).limit(5000))
    for check in checks:
        site = intel.site_key(session, check.host or "", check.domain)
        if not site:  # a check stored without a host (an early skeleton row) has no case to open
            continue
        case = cases.setdefault(site, Case(site))
        if case.latest is None:
            case.latest = check
        case.checks += 1
        case.sources.add(check.source)
        case.last_seen = _later(case.last_seen, check.created_at)
    for site, count, last in session.execute(
        select(Report.domain, func.count(), func.max(Report.created_at)).where(Report.created_at >= since).group_by(Report.domain)
    ):
        if site:
            case = cases.setdefault(site, Case(site))
            case.reports, case.last_seen = count, _later(case.last_seen, last)
            case.sources.add("user_report")
    for site, source_name, last in session.execute(
        select(FeedEntry.domain, FeedEntry.source, func.max(FeedEntry.first_seen))
        .where(FeedEntry.first_seen >= since).group_by(FeedEntry.domain, FeedEntry.source)
    ):
        case = cases.setdefault(site, Case(site))
        case.feeds.add(source_name)
        case.sources.add("hunter")
        case.last_seen = _later(case.last_seen, last)
    if not cases:
        return cases

    sites = list(cases)
    for site, total in session.execute(select(Hit.domain, func.sum(Hit.count)).where(Hit.domain.in_(sites)).group_by(Hit.domain)):
        cases[site].hits = int(total or 0)
    for row in session.scalars(select(Domain).where(Domain.domain.in_(sites))):
        cases[row.domain].status, cases[row.domain].status_source = row.status, row.source
    missing = [site for site, case in cases.items() if case.latest is None]
    if missing:
        for check in session.scalars(
            select(Check).where((Check.domain.in_(missing)) | (Check.host.in_(missing))).order_by(Check.created_at.desc())
        ):
            site = check.host if check.host in cases else check.domain
            if site in cases and cases[site].latest is None:
                cases[site].latest = check
    return cases


def reviewed_sites(session: Session, sites: list[str]) -> set[str]:
    rows = session.execute(
        select(Check.domain, Check.host).join(Evidence, Evidence.check_id == Check.id).join(Review, Review.evidence_id == Evidence.id)
        .where((Check.domain.in_(sites)) | (Check.host.in_(sites)))
    ).all()
    return {value for row in rows for value in row if value in sites}


def ranked(session: Session, now: datetime | None = None, source: str | None = None, brand: str | None = None,
           band_filter: str | None = None, has_reports: bool | None = None, auto: bool = False) -> list[Case]:
    now = now or datetime.now(UTC)
    cases = collect(session, now, include_batch=source == "batch")
    reviewed = reviewed_sites(session, list(cases)) if auto else set()
    kept = []
    for case in cases.values():
        if auto:
            if case.status != "confirmed" or case.status_source == "officer" or case.site in reviewed:
                continue
        elif case.status in DECIDED:
            continue
        if source and source not in case.sources and source not in case.feeds:
            continue
        if brand and (case.latest is None or case.latest.brand_id != brand):
            continue
        if band_filter and band(case.score) != band_filter:
            continue
        if has_reports is not None and (case.reports > 0) != has_reports:
            continue
        kept.append(case)
    kept.sort(key=lambda c: (c.priority(now), c.tiebreak(now), c.site), reverse=True)
    return kept


def row(case: Case, now: datetime) -> dict:
    check = case.latest
    return {
        "domain": case.site, "display": defang(case.site),
        "priority": round(case.priority(now), 2), "rank_score": round(case.tiebreak(now), 2),
        "score": case.score, "band": band(case.score), "verdict": check.verdict if check else None,
        "stage": check.stage if check else None, "brand": check.brand if check else None,
        "brand_id": check.brand_id if check else None,
        "check_id": check.id if check else None, "evidence_id": check.evidence_id if check else None,
        "campaign_id": check.campaign_id if check else None,
        "preview": f"/v1/preview/{check.evidence_id}.png" if check and check.evidence_id and check.preview else None,
        "reports": case.reports, "hits": case.hits, "checks": case.checks,
        "sources": sorted(case.sources), "feeds": sorted(case.feeds), "status": case.status,
        "last_seen": case.last_seen.isoformat() if case.last_seen else None,
        "top_reasons": [{"code": r["code"], "weight": r["weight"], "en": r["en"]} for r in sorted(
            check.reasons or [], key=lambda r: -(r["weight"] or 0))[:3]] if check else [],
    }


def page(session: Session, cursor: str | None = None, **filters) -> dict:
    now = datetime.now(UTC)
    cases = ranked(session, now, **filters)
    start = int(cursor) if cursor and cursor.isdigit() else 0
    chunk = cases[start : start + PAGE]
    following = start + PAGE if start + PAGE < len(cases) else None
    return {"total": len(cases), "cases": [row(case, now) for case in chunk],
            "next_cursor": str(following) if following is not None else None}


def case_detail(session: Session, site: str) -> dict | None:
    checks = session.scalars(
        select(Check).where((Check.domain == site) | (Check.host == site)).order_by(Check.created_at.desc()).limit(20)
    ).all()
    feeds = session.scalars(select(FeedEntry).where(FeedEntry.domain == site).order_by(FeedEntry.first_seen)).all()
    report_rows = session.scalars(select(Report).where(Report.domain == site).order_by(Report.created_at.desc())).all()
    if not checks and not feeds and not report_rows:
        return None
    latest = checks[0] if checks else None
    evidence = session.get(Evidence, latest.evidence_id) if latest and latest.evidence_id else None
    payload = evidence.payload if evidence else {}
    discovery, seen = [], set()
    for entry in feeds:
        if entry.source not in seen:
            seen.add(entry.source)
            discovery.append({"source": entry.source, "first_seen": entry.first_seen.isoformat(), "url": entry.url,
                              "display_url": defang(entry.url), "brand_id": entry.brand_id})
    reviews = session.execute(
        select(Review).join(Evidence, Evidence.id == Review.evidence_id).join(Check, Check.id == Evidence.check_id)
        .where((Check.domain == site) | (Check.host == site)).order_by(Review.reviewed_at.desc())
    ).scalars().all()
    campaign = session.get(Campaign, latest.campaign_id) if latest and latest.campaign_id else None
    domain_row = session.get(Domain, site)
    watched = session.get(Watchlist, site)
    hits = {channel: count for channel, count in session.execute(select(Hit.channel, Hit.count).where(Hit.domain == site))}
    return {
        "domain": site, "display": defang(site),
        "status": domain_row.status if domain_row else None, "status_source": domain_row.source if domain_row else None,
        "latest": None if latest is None else {
            "check_id": latest.id, "url": latest.url, "display_url": defang(latest.url),
            "final_url": latest.final_url, "display_final_url": defang(latest.final_url),
            "verdict": latest.verdict, "score": latest.score, "stage": latest.stage, "brand": latest.brand,
            "brand_id": latest.brand_id, "reasons": latest.reasons, "sources": latest.sources, "features": latest.features,
            "safe_action": latest.safe_action, "deep_status": latest.deep_status, "evidence_id": latest.evidence_id,
            "preview": latest.preview, "created_at": latest.created_at.isoformat(),
        },
        "page": payload.get("page"), "infra": payload.get("infra"), "visual": payload.get("visual"), "kit": payload.get("kit"),
        "discovery": discovery,
        "reports": {"count": len(report_rows), "notes": [{"at": r.created_at.isoformat(), "note": r.note} for r in report_rows if r.note][:20]},
        "hits": hits,
        "campaign": None if campaign is None else {"id": campaign.id, "name": campaign.name, "domain_count": campaign.domain_count,
                                                   "confirmed_count": campaign.confirmed_count},
        "watchlist": None if watched is None else {"reason": watched.reason, "last_status": watched.last_status,
                                                   "next_check_at": watched.next_check_at.isoformat(),
                                                   "expires_at": watched.expires_at.isoformat()},
        "reviews": [{"decision": r.decision, "reason": r.reason, "reviewer": r.reviewer, "note": r.note,
                     "at": r.reviewed_at.isoformat(), "evidence_id": r.evidence_id} for r in reviews],
        "history": [{"check_id": c.id, "source": c.source, "verdict": c.verdict, "score": c.score, "stage": c.stage,
                     "at": c.created_at.isoformat()} for c in checks],
    }
