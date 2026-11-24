"""The officer review queue (docs/admin-dashboard.md, "Queue"): one case per site, ranked.

A case is a site (registrable domain, or the full host on a shared platform; docs/app-plan.md decision 14)
with a warn or block check, a resident report or a Hunter feed entry in the last 14 days. Official,
allowlisted and cleared sites never appear. Each case has a state: `open`, `auto_confirmed` (the deep job
confirmed it; an officer can undo that), `confirmed` or `rejected` (an officer rejected it and no old check
brings it back). The default view is `open`. Checks from the judges' `/v1/batch` route are evaluation traffic,
not sightings: they only show with `source=batch`.

Only an officer can clear a case. Its representative check is the highest-scoring evidence since the last
officer re-run (all evidence if there was none), so an anonymous or resident clean check, however recent,
never lowers what the officer sees; only an officer re-run that comes back clean takes the case out.

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
from app.infra import location
from app.models import Campaign, Check, Domain, Evidence, FeedEntry, Hit, Report, Review, Watchlist
from app.review import confirmer
from app.takedown import tracker
from app.verdict.bands import band

WINDOW = timedelta(days=14)
PAGE = 50
HIDDEN = ("official", "allowlisted", "cleared")
STATES = ("open", "auto_confirmed", "all")
FLAGGED = ("warn", "block")


@dataclass
class Case:
    site: str
    checks: list[Check] = field(default_factory=list)  # newest first, every check on the site
    latest: Check | None = None  # the representative check: what the officer sees
    last_seen: datetime | None = None
    flagged: int = 0
    sources: set[str] = field(default_factory=set)
    reports: int = 0
    hits: int = 0
    feeds: set[str] = field(default_factory=set)
    status: str | None = None
    status_source: str | None = None
    confirmed_by: str | None = None
    reviews: list[Review] = field(default_factory=list)  # newest first

    @property
    def score(self) -> int:
        return self.latest.score if self.latest else 0

    @property
    def state(self) -> str:
        if self.status == "confirmed":
            return "auto_confirmed" if self.confirmed_by == "auto" else "confirmed"
        if self.reviews and self.reviews[0].decision == "reject":
            return "rejected"
        return "open"

    @property
    def cleared_by_officer(self) -> bool:
        """The representative is an officer re-run that came back clean."""
        return self.latest is not None and self.latest.source == "officer" and self.latest.verdict not in (*FLAGGED, "pending")

    @property
    def in_queue(self) -> bool:
        if self.reports:
            return True
        if self.cleared_by_officer:
            return False
        return bool(self.feeds) or self.latest is None or self.latest.verdict in FLAGGED

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


def representative(checks: list[Check]) -> Check | None:
    """The highest-scoring evidence-bearing check since the latest officer re-run (all of it if there was none).

    A re-run still waiting for its evidence leaves the earlier evidence in place. Without any evidence, the
    highest-scoring check that is not an officer re-run stands in. `checks` is newest first.
    """
    if not checks:
        return None
    with_evidence = [c for c in checks if c.evidence_id]
    since = max((c.created_at for c in checks if c.source == "officer"), default=None)
    pool = [c for c in with_evidence if since is None or c.created_at >= since] or with_evidence
    if not pool:
        pool = [c for c in checks if c.source != "officer"] or checks
    return max(reversed(pool), key=lambda c: c.score)


def collect(session: Session, now: datetime, include_batch: bool = False, only: str | None = None,
            window: timedelta | None = WINDOW) -> dict[str, Case]:
    """The cases by site. With `only`, that one site whatever it has (the case card), without the window;
    `window=None` looks at everything ever seen (the helplines list)."""
    since = None if only else (now - window if window else None)
    cases: dict[str, Case] = {}

    def not_batch(query):
        return query if include_batch or only else query.where(Check.source != "batch")

    if only:
        cases[only] = Case(only)
    else:
        flagged = select(Check.host, Check.domain).where(Check.verdict.in_(FLAGGED))
        if since:
            flagged = flagged.where(Check.created_at >= since)
        for host, domain in session.execute(not_batch(flagged).order_by(Check.created_at.desc()).limit(5000)):
            site = intel.site_key(session, host or "", domain)
            if site:  # a check stored without a host (an early skeleton row) has no case to open
                cases.setdefault(site, Case(site))
    report_query = select(Report.domain, func.count(), func.max(Report.created_at)).group_by(Report.domain)
    feed_query = select(FeedEntry.domain, FeedEntry.source, func.max(FeedEntry.first_seen)).group_by(FeedEntry.domain, FeedEntry.source)
    if only:
        report_query, feed_query = report_query.where(Report.domain == only), feed_query.where(FeedEntry.domain == only)
    elif since:
        report_query, feed_query = report_query.where(Report.created_at >= since), feed_query.where(FeedEntry.first_seen >= since)
    for site, count, last in session.execute(report_query):
        if site:
            case = cases.setdefault(site, Case(site))
            case.reports, case.last_seen = count, _later(case.last_seen, last)
            case.sources.add("user_report")
    for site, source_name, last in session.execute(feed_query):
        case = cases.setdefault(site, Case(site))
        case.feeds.add(source_name)
        case.sources.add("hunter")
        case.last_seen = _later(case.last_seen, last)
    if not cases:
        return cases

    sites = list(cases)

    def owner(host: str | None, domain: str | None) -> str | None:
        return next((value for value in (intel.site_key(session, host or "", domain), host, domain) if value in cases), None)

    check_query = not_batch(select(Check).where((Check.domain.in_(sites)) | (Check.host.in_(sites))))
    for check in session.scalars(check_query.order_by(Check.created_at.desc()).limit(50000)):
        site = owner(check.host, check.domain)
        if site is None:
            continue
        case = cases[site]
        case.checks.append(check)
        if check.verdict in FLAGGED and (since is None or check.created_at >= since):
            case.flagged += 1
            case.sources.add(check.source)
            case.last_seen = _later(case.last_seen, check.created_at)
    for site, total in session.execute(select(Hit.domain, func.sum(Hit.count)).where(Hit.domain.in_(sites)).group_by(Hit.domain)):
        cases[site].hits = int(total or 0)
    for row in session.scalars(select(Domain).where(Domain.domain.in_(sites))):
        case = cases[row.domain]
        case.status, case.status_source, case.confirmed_by = row.status, row.source, confirmer(row)
    reviews = session.execute(
        select(Review, Check.host, Check.domain).join(Evidence, Evidence.id == Review.evidence_id)
        .join(Check, Check.id == Evidence.check_id).where((Check.domain.in_(sites)) | (Check.host.in_(sites)))
        .order_by(Review.id.desc())
    )
    for review, host, domain in reviews:
        site = owner(host, domain)
        if site is not None:
            cases[site].reviews.append(review)
    for case in cases.values():
        case.latest = representative(case.checks)
        if only and case.last_seen is None and case.checks:
            case.last_seen = case.checks[0].created_at
    return cases


def ranked(session: Session, now: datetime | None = None, source: str | None = None, brand: str | None = None,
           band_filter: str | None = None, has_reports: bool | None = None, auto: bool = False,
           state: str = "open") -> list[Case]:
    """`state` is open, auto_confirmed or all; `auto=True` is the older spelling of auto_confirmed."""
    now = now or datetime.now(UTC)
    if auto:
        state = "auto_confirmed"
    cases = collect(session, now, include_batch=source == "batch")
    kept = []
    for case in cases.values():
        if case.status in HIDDEN:
            continue
        if state == "auto_confirmed" and case.state != "auto_confirmed":
            continue
        if state == "open" and (case.state != "open" or not case.in_queue):
            continue
        if state == "all" and case.state == "open" and not case.in_queue:
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
        "domain": case.site, "display": defang(case.site), "state": case.state,
        "priority": round(case.priority(now), 2), "rank_score": round(case.tiebreak(now), 2),
        "score": case.score, "band": band(case.score), "verdict": check.verdict if check else None,
        "stage": check.stage if check else None, "brand": check.brand if check else None,
        "brand_id": check.brand_id if check else None,
        "check_id": check.id if check else None, "evidence_id": check.evidence_id if check else None,
        "campaign_id": check.campaign_id if check else None,
        "preview": f"/v1/preview/{check.evidence_id}.png" if check and check.evidence_id and check.preview else None,
        "reports": case.reports, "hits": case.hits, "checks": case.flagged,
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


def has_screenshot(payload: dict, check: Check | None) -> bool:
    kinds = {item.get("kind") for item in payload.get("artifacts") or []}
    return bool(kinds & {"screenshot", "full_screenshot"}) or bool(check is not None and check.preview)


def case_detail(session: Session, site: str) -> dict | None:
    now = datetime.now(UTC)
    case = collect(session, now, only=site)[site]
    feeds = session.scalars(select(FeedEntry).where(FeedEntry.domain == site).order_by(FeedEntry.first_seen)).all()
    report_rows = session.scalars(select(Report).where(Report.domain == site).order_by(Report.created_at.desc())).all()
    checks = case.checks
    if not checks and not feeds and not report_rows:
        return None
    latest = case.latest
    evidence = session.get(Evidence, latest.evidence_id) if latest and latest.evidence_id else None
    payload = evidence.payload if evidence else {}
    infra = payload.get("infra") or {}
    discovery, seen = [], set()
    for entry in feeds:
        if entry.source not in seen:
            seen.add(entry.source)
            discovery.append({"source": entry.source, "first_seen": entry.first_seen.isoformat(), "url": entry.url,
                              "display_url": defang(entry.url), "brand_id": entry.brand_id})
    campaign = session.get(Campaign, latest.campaign_id) if latest and latest.campaign_id else None
    domain_row = session.get(Domain, site)
    watched = session.get(Watchlist, site)
    hits = {channel: count for channel, count in session.execute(select(Hit.channel, Hit.count).where(Hit.domain == site))}
    first_check = min((c.created_at for c in checks), default=None)
    first_seen = min([t for t in (first_check, *(f.first_seen for f in feeds), *(r.created_at for r in report_rows)) if t])
    return {
        "domain": site, "display": defang(site), "state": case.state,
        "status": domain_row.status if domain_row else None, "status_source": domain_row.source if domain_row else None,
        "confirmed_by": case.confirmed_by,
        "url": latest.url if latest else None, "final_url": latest.final_url if latest else None,
        "title": (payload.get("page") or {}).get("title"),
        "reasons": (latest.reasons if latest else None) or payload.get("reasons") or [],
        "evidence_id": latest.evidence_id if latest else None,
        "campaign_id": latest.campaign_id if latest else None,
        "sources": sorted(case.sources), "report_count": len(report_rows), "hit_count": case.hits,
        "first_seen": first_seen.isoformat(), "last_seen": case.last_seen.isoformat() if case.last_seen else None,
        "rank": round(case.priority(now), 2), "has_screenshot": has_screenshot(payload, latest),
        "location": location(infra) if infra else None,
        "lead_time": tracker.lead_time(first_check, domain_row, watched) if first_check else None,
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
        "reports": {"count": len(report_rows),
                    "notes": [{"id": r.id, "note": r.note, "created_at": r.created_at.isoformat()} for r in report_rows if r.note][:20]},
        "hits": hits,
        "campaign": None if campaign is None else {"id": campaign.id, "name": campaign.name, "domain_count": campaign.domain_count,
                                                   "confirmed_count": campaign.confirmed_count},
        "watchlist": None if watched is None else {"reason": watched.reason, "last_status": watched.last_status,
                                                   "next_check_at": watched.next_check_at.isoformat(),
                                                   "expires_at": watched.expires_at.isoformat()},
        "reviews": [{"decision": r.decision, "reason": r.reason, "reviewer": r.reviewer, "note": r.note,
                     "at": r.reviewed_at.isoformat(), "evidence_id": r.evidence_id} for r in case.reviews],
        "history": [{"check_id": c.id, "source": c.source, "verdict": c.verdict, "score": c.score, "stage": c.stage,
                     "at": c.created_at.isoformat()} for c in checks[:20]],
    }
