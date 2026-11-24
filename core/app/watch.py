import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import queue
from app.checks import run_check
from app.config import Settings, get_settings
from app.db import get_session
from app.models import Check, Watchlist
from app.schemas import FeedResponse, WatchRunResponse

router = APIRouter()
logger = logging.getLogger(__name__)

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
RECHECK_AFTER = timedelta(hours=6)
VT_REFRESH = timedelta(hours=24)
POLL_TIMEOUT = 5
SAFE_BROWSING_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
VIRUSTOTAL_URL = "https://www.virustotal.com/api/v3/domains/"


def log_failure(service: str, domain: str, error: Exception) -> None:
    """Log the status code or the exception class only: an httpx message carries the request URL, key included."""
    reason = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else type(error).__name__
    logger.warning("%s poll failed for %s: %s", service, domain, reason)


def poll_safe_browsing(key: str, domain: str) -> bool | None:
    """True when Google lists the domain, False when it does not, None when the poll failed."""
    body = {
        "client": {"clientId": "kartoshka-police", "clientVersion": "1"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": f"https://{domain}/"}],
        },
    }
    try:
        response = httpx.post(SAFE_BROWSING_URL, params={"key": key}, json=body, timeout=POLL_TIMEOUT)
        response.raise_for_status()
        return bool(response.json().get("matches"))
    except (httpx.HTTPError, ValueError) as error:
        log_failure("Safe Browsing", domain, error)
        return None


def poll_virustotal(key: str, domain: str) -> bool | None:
    """True when at least one engine calls the domain malicious, False when none does, None when the poll failed."""
    try:
        response = httpx.get(VIRUSTOTAL_URL + domain, headers={"x-apikey": key}, timeout=POLL_TIMEOUT)
        response.raise_for_status()
        return response.json()["data"]["attributes"]["last_analysis_stats"]["malicious"] > 0
    except (httpx.HTTPError, ValueError, KeyError) as error:
        log_failure("VirusTotal", domain, error)
        return None


def record_poll(row: Watchlist, prefix: str, hit: bool, now: datetime) -> None:
    if hit:
        if getattr(row, f"{prefix}_first_hit_at") is None:
            setattr(row, f"{prefix}_first_hit_at", now)
    elif getattr(row, f"{prefix}_first_hit_at") is None:
        setattr(row, f"{prefix}_last_clean_at", now)


def poll_row(row: Watchlist, settings: Settings, now: datetime) -> None:
    if settings.google_safe_browsing_api_key:
        hit = poll_safe_browsing(settings.google_safe_browsing_api_key, row.domain)
        if hit is not None:
            record_poll(row, "gsb", hit, now)
    vt_stale = row.vt_checked_at is None or now - row.vt_checked_at > VT_REFRESH
    if settings.virustotal_api_key and vt_stale:
        hit = poll_virustotal(settings.virustotal_api_key, row.domain)
        if hit is not None:
            record_poll(row, "vt", hit, now)
            row.vt_checked_at = now


def lead_time_of(first_seen: datetime, first_hit_at: datetime | None, last_clean_at: datetime | None) -> dict:
    clean = last_clean_at if last_clean_at and (first_hit_at is None or last_clean_at < first_hit_at) else None
    hours = max(int((clean - first_seen).total_seconds() // 3600), 0) if clean else None
    if first_hit_at:
        return {"state": "hit", "at_least_hours": hours or 0}
    if clean:
        return {"state": "ahead", "at_least_hours": hours}
    return {"state": "not_polled", "at_least_hours": None}


def lead_time(first_seen: datetime, watch_row: Watchlist) -> dict:
    """How long the domain was watched before each service listed it. Hours are a lower bound."""
    return {
        "gsb": lead_time_of(first_seen, watch_row.gsb_first_hit_at, watch_row.gsb_last_clean_at),
        "vt": lead_time_of(first_seen, watch_row.vt_first_hit_at, watch_row.vt_last_clean_at),
    }


@router.get("/feed", response_model=FeedResponse)
def feed(session: SessionDep, limit: Annotated[int, Query(ge=1, le=200)] = 50) -> FeedResponse:
    checks = session.scalars(
        select(Check).where(Check.source == "hunter").order_by(Check.created_at.desc()).limit(limit)
    )
    return FeedResponse(items=checks.all())


@router.post("/watchlist/run", response_model=WatchRunResponse, status_code=202)
def run_watchlist(session: SessionDep, settings: SettingsDep) -> WatchRunResponse:
    now = datetime.now(UTC)
    due = session.scalars(
        select(Watchlist).where(Watchlist.next_check_at <= now, Watchlist.expires_at > now)
    ).all()
    for row in due:
        check = run_check(session, f"https://{row.domain}/", "watchlist", "deep", settings.data_dir)
        poll_row(row, settings, now)
        row.next_check_at = now + RECHECK_AFTER
        session.commit()
        if check.verdict == "pending":
            queue.enqueue_deep_check(check.id)
    return WatchRunResponse(queued=len(due))
