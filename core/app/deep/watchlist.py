"""Parked or unreachable domains are not safe: re-check them every 6 hours for 14 days (ARCHITECTURE.md 1.3).

`run_due` is called by the hunter's watchlist ticker through `POST /v1/watchlist/run`, or by hand:
    python -m app.deep.watchlist
"""
import asyncio
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Watchlist

EVERY = timedelta(hours=6)
WATCH_FOR = timedelta(days=14)


def add(session: Session, domain: str, url: str, reason_code: str, brand_id: str | None, now: datetime | None = None) -> None:
    """Start watching, or keep watching with the newest URL. The 14 days run from the first sighting."""
    now = now or datetime.now(UTC)
    statement = insert(Watchlist).values(
        domain=domain, url=url, reason=reason_code, brand_id=brand_id, last_status=reason_code.lower(),
        last_checked_at=now, offline_since=now if reason_code == "UNREACHABLE" else None,
        next_check_at=now + EVERY, expires_at=now + WATCH_FOR, checks_done=0,
    )
    session.execute(statement.on_conflict_do_update(
        index_elements=[Watchlist.domain],
        set_={"url": url, "reason": reason_code, "last_status": reason_code.lower(), "last_checked_at": now,
              "brand_id": statement.excluded.brand_id},
    ))


def seen_live(session: Session, domain: str, now: datetime | None = None) -> None:
    """A watched domain now serves a real page; it stays watched until it expires."""
    row = session.get(Watchlist, domain)
    if row is not None:
        row.last_status, row.last_checked_at, row.offline_since = "live", now or datetime.now(UTC), None


def due(session: Session, now: datetime | None = None, limit: int = 50) -> list[Watchlist]:
    now = now or datetime.now(UTC)
    return list(session.scalars(
        select(Watchlist).where(Watchlist.next_check_at <= now, Watchlist.expires_at > now)
        .order_by(Watchlist.next_check_at).limit(limit)
    ))


async def run_due(session: Session, settings: Settings, now: datetime | None = None, limit: int = 50) -> list[str]:
    """Queue a deep re-check of every due domain. Returns the new check ids."""
    from app.verdict.service import run_check

    now = now or datetime.now(UTC)
    rows = due(session, now, limit)
    for row in rows:
        row.next_check_at = now + EVERY
        row.checks_done += 1
    session.commit()
    ids = []
    for row in rows:
        check = await run_check(session, row.url or f"https://{row.domain}/", "watchlist", "deep", settings, force_deep=True)
        ids.append(check.id)
    return ids


if __name__ == "__main__":
    from app.db import get_engine

    with Session(get_engine()) as db:
        queued = asyncio.run(run_due(db, get_settings()))
    print(f"queued {len(queued)} watchlist re-checks")
    sys.exit(0)
