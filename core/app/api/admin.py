"""Officer console routes, D1 (docs/admin-dashboard.md). Every route needs the write token, reads included:
they show reason weights and Hunter internals that residents never see."""
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit, cache, queue
from app import review as decisions
from app.admin import queue as cases
from app.admin import stats as kpi
from app.auth import require_write_token
from app.deep import watchlist
from app.deep.visual import REFS_KEY
from app.defang import defang
from app.deps import SessionDep, SettingsDep
from app.fast import intel
from app.helplines import routes as helplines
from app.models import Check, Evidence, FeedEntry, ModelState, Watchlist

router = APIRouter(prefix="/admin", dependencies=[Depends(require_write_token)])
router.include_router(helplines.router)
PAGE = 50


def flagged_check(session: Session, site: str) -> Check | None:
    """The check an officer re-runs: the case's representative (the flagged URL), not the latest one seen."""
    case = cases.collect(session, datetime.now(UTC), only=site)[site]
    return case.latest


@router.get("/queue", description="Ranked review queue, one case per site, each with its state (open, auto_confirmed, "
            "confirmed, rejected). `state` is open (default), auto_confirmed or all; `auto=true` is the older spelling of "
            "auto_confirmed. Cursor-paginated, 50 rows per page.")
def review_queue(
    session: SessionDep,
    source: str | None = None,
    brand: str | None = None,
    band: Annotated[str | None, Query(pattern="^(allow|warn|block)$")] = None,
    has_reports: bool | None = None,
    auto: bool = False,
    state: Literal["open", "auto_confirmed", "all"] = "open",
    cursor: str | None = None,
) -> dict:
    return cases.page(session, cursor, source=source, brand=brand, band_filter=band, has_reports=has_reports, auto=auto,
                      state=state)


@router.get("/cases/{domain}", description="The case card: latest check, page, infrastructure, discovery, reports, "
            "hits, campaign, watchlist and previous reviews.")
def case(domain: str, session: SessionDep) -> dict:
    body = cases.case_detail(session, domain.lower())
    if body is None:
        raise HTTPException(404, "Unknown case")
    return body


class OfficerAction(BaseModel):
    reviewer: str = Field("Demo Officer", max_length=200)
    note: str = Field("", max_length=2000)


@router.post("/cases/{domain}/recheck", description="Run a fresh deep check of the latest URL of this case.")
async def recheck(domain: str, body: OfficerAction, session: SessionDep, settings: SettingsDep) -> dict:
    check = flagged_check(session, domain.lower())
    if check is None:
        raise HTTPException(404, "Unknown case")
    fresh = await run_officer_check(session, settings, check.url)
    audit.record(session, body.reviewer, "case.recheck", "domain", domain.lower(), None, {"check_id": fresh.id}, body.note or None)
    session.commit()
    return {"check_id": fresh.id, "deep_status": fresh.deep_status, "verdict": fresh.verdict, "score": fresh.score}


async def run_officer_check(session: Session, settings, url: str) -> Check:
    from app.verdict.service import run_check

    return await run_check(session, url, "officer", "deep", settings, force_deep=True)


@router.post("/cases/{domain}/watch", description="Put the site on the watchlist: a deep re-check every 6 hours for 14 days.")
def watch(domain: str, body: OfficerAction, session: SessionDep) -> dict:
    site = domain.lower()
    check = flagged_check(session, site)
    if check is None:
        raise HTTPException(404, "Unknown case")
    site = intel.site_key(session, check.host or "", check.domain)
    before = session.get(Watchlist, site)
    watchlist.add(session, site, check.url, "OFFICER_WATCH", check.brand_id)
    audit.record(session, body.reviewer, "case.watch", "domain", site,
                 {"watched": before is not None}, {"watched": True}, body.note or None)
    session.commit()
    row = session.get(Watchlist, site)
    return {"domain": site, "display": defang(site), "next_check_at": row.next_check_at.isoformat(),
            "expires_at": row.expires_at.isoformat()}


@router.post("/cases/{domain}/undo-auto-confirm", description="Take an automatic confirmation off the site; the case "
             "is open again. Refused for a site an officer confirmed.")
def undo_auto_confirm(domain: str, body: OfficerAction, session: SessionDep) -> dict:
    site = domain.lower()
    try:
        decisions.undo_auto_confirm(session, site, body.reviewer, body.note or None)
    except decisions.ReviewRefused as refused:
        raise HTTPException(409, str(refused)) from None
    session.commit()
    return {"domain": site, "state": cases.collect(session, datetime.now(UTC), only=site)[site].state}


@router.get("/audit", description="The audit log, newest first, optionally for one target. 100 rows by default, 500 at most.")
def audit_list(session: SessionDep, target: str | None = None, limit: Annotated[int, Query(ge=1, le=500)] = 100) -> dict:
    return {"entries": audit.recent(session, target, limit)}


@router.get("/hunter/feed", description="Hunter candidates, newest first. Each row carries the site's latest verdict, if checked.")
def hunter_feed(
    session: SessionDep,
    since: datetime | None = None,
    brand: str | None = None,
    source: str | None = None,
    cursor: int | None = None,
) -> dict:
    query = select(FeedEntry).order_by(FeedEntry.id.desc()).limit(PAGE)
    if since is not None:
        query = query.where(FeedEntry.first_seen > since)
    if brand:
        query = query.where(FeedEntry.brand_id == brand)
    if source:
        query = query.where(FeedEntry.source == source)
    if cursor:
        query = query.where(FeedEntry.id < cursor)
    rows = session.scalars(query).all()
    sites = list({row.domain for row in rows})
    verdicts = {}
    if sites:
        for check in session.scalars(select(Check).where(Check.domain.in_(sites)).order_by(Check.created_at)):
            verdicts[check.domain] = check
    entries = []
    for row in rows:
        check = verdicts.get(row.domain)
        entries.append({
            "id": row.id, "source": row.source, "domain": row.domain, "display": defang(row.domain),
            "display_url": defang(row.url), "brand_id": row.brand_id, "detail": row.detail,
            "first_seen": row.first_seen.isoformat(),
            "verdict": check.verdict if check else None, "score": check.score if check else None,
            "stage": check.stage if check else None,
        })
    return {"entries": entries, "next_cursor": rows[-1].id if len(rows) == PAGE else None}


@router.get("/watchlist", description="Watched sites: parked, unreachable, or put there by an officer.")
def watched(session: SessionDep, cursor: int = 0) -> dict:
    now = datetime.now(UTC)
    rows = session.scalars(
        select(Watchlist).where(Watchlist.expires_at > now).order_by(Watchlist.next_check_at).offset(cursor).limit(PAGE)
    ).all()
    total = session.scalar(select(func.count()).select_from(Watchlist).where(Watchlist.expires_at > now))
    return {
        "total": total,
        "entries": [{
            "domain": row.domain, "display": defang(row.domain), "display_url": defang(row.url), "reason": row.reason,
            "brand_id": row.brand_id, "last_status": row.last_status,
            "last_checked_at": row.last_checked_at.isoformat() if row.last_checked_at else None,
            "offline_since": row.offline_since.isoformat() if row.offline_since else None,
            "checks_done": row.checks_done, "next_check_at": row.next_check_at.isoformat(),
            "expires_at": row.expires_at.isoformat(),
        } for row in rows],
        "next_cursor": cursor + PAGE if cursor + PAGE < total else None,
    }


@router.get("/stats", description="Impact KPIs for 24 hours or 7 days (volumes, a time series for the chart, lead time "
            "per confirmed CT-sighted domain against GSB and VirusTotal) and model quality against officer decisions.")
def stats(session: SessionDep, range: Annotated[str, Query(pattern="^(24h|7d)$")] = "24h") -> dict:
    return {**kpi.impact(session, range), "quality": kpi.quality(session)}


@router.get("/health", description="System strip for the console: database, redis, deep queue, Hunter freshness, models.")
def health(session: SessionDep, settings: SettingsDep) -> dict:
    now = datetime.now(UTC)
    out: dict = {"checked_at": now.isoformat()}
    try:
        work = queue.get_queue()
        out["deep_queue"] = {"waiting": len(work), "failed": work.failed_job_registry.count,
                             "workers": len(work.connection.smembers("rq:workers"))}
        out["redis"] = "ok"
    except Exception as error:
        out["redis"] = f"error: {type(error).__name__}"
    last_feed = session.execute(
        select(FeedEntry.source, func.max(FeedEntry.first_seen), func.count()).where(
            FeedEntry.first_seen >= now - timedelta(hours=24)).group_by(FeedEntry.source)
    ).all()
    out["hunter"] = {source: {"last": last.isoformat(), "last_24h": count} for source, last, count in last_feed}
    last_check = session.scalar(select(func.max(Check.created_at)))
    stale_from = now - timedelta(seconds=queue.DEEP_LOCK_S)
    out["checks"] = {
        "last": last_check.isoformat() if last_check else None,
        "last_hour": session.scalar(select(func.count()).select_from(Check).where(Check.created_at >= now - timedelta(hours=1))),
        "deep_running": session.scalar(select(func.count()).select_from(Check).where(
            Check.deep_status.in_(("queued", "running")), Check.updated_at >= stale_from)),
        # queued or running for longer than a deep job may take: the job was lost (worker restart, old job name)
        "deep_stale": session.scalar(select(func.count()).select_from(Check).where(
            Check.deep_status.in_(("queued", "running")), Check.updated_at < stale_from)),
    }
    models = {}
    for key in ("url_model", REFS_KEY):
        row = session.get(ModelState, key)
        models[key] = None if row is None else {"updated_at": row.updated_at.isoformat(), "score": row.score}
    out["models"] = models
    out["evidence"] = {"records": session.scalar(select(func.count()).select_from(Evidence))}
    out["blocklist_version"] = cache.blocklist_version()
    out["ai"] = "configured" if settings.ai_provider and settings.anthropic_api_key else "not configured"
    return out
