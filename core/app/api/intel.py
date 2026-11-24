"""Machine intake, write token required: Hunter candidates, watchlist ticks, DNS Shield block counters."""
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app import cache
from app.auth import require_write_token
from app.deep import watchlist
from app.deps import SessionDep, SettingsDep
from app.models import FeedEntry
from app.normalize.url import normalize
from app.verdict.service import count_hit, run_check

router = APIRouter(dependencies=[Depends(require_write_token)])
MAX_CHECKS = 50


class FeedItem(BaseModel):
    source: str = Field(max_length=40, description="ct, nrd, openphish, phishtank, phishing_army, urlhaus, search, ...")
    url: str = Field(max_length=4096)
    brand_id: str | None = Field(None, max_length=40)
    detail: str | None = Field(None, max_length=2000)


class FeedBatch(BaseModel):
    entries: list[FeedItem] = Field(max_length=2000)
    check: bool = Field(False, description=f"Also run a check (fast, then deep) on up to {MAX_CHECKS} new entries")
    check_mode: Literal["deep", "screen"] = Field(
        "deep", description="`deep`: every checked entry gets a deep analysis. `screen` (high-volume sources such as CT): "
        "only entries whose fast score is 30 or more do, so the sandbox is not flooded.")


@router.post("/intel/feeds", description="Hunter intake. New entries are stored once per (source, url) and announced "
             "as `hunter.candidate`; with `check: true` they are also checked.")
async def feeds(body: FeedBatch, session: SessionDep, settings: SettingsDep) -> dict:
    inserted = []
    for item in body.entries:
        try:
            n = normalize(item.url)
        except ValueError:
            continue
        if not n.is_ip and not n.tld:
            continue
        statement = insert(FeedEntry).values(source=item.source, url=n.url, domain=n.domain or n.host,
                                             brand_id=item.brand_id, detail=item.detail)
        row = session.execute(statement.on_conflict_do_nothing(index_elements=[FeedEntry.source, FeedEntry.url])
                              .returning(FeedEntry.id, FeedEntry.first_seen)).first()
        if row is not None:
            inserted.append((item, n, row.first_seen))
    session.commit()

    spikes = {}
    for item, n, first_seen in inserted:
        cache.publish({"type": "hunter.candidate", "source": item.source, "domain": n.domain or n.host,
                       "brand_id": item.brand_id, "first_seen": first_seen.isoformat()})
        if item.brand_id:
            spikes[item.brand_id] = spikes.get(item.brand_id, 0) + 1
    since = datetime.now(UTC) - timedelta(hours=1)
    for brand_id in spikes:
        count = session.scalar(select(func.count()).select_from(FeedEntry)
                               .where(FeedEntry.brand_id == brand_id, FeedEntry.first_seen >= since))
        if count >= settings.brand_spike_per_hour and cache.sync_client_once(f"kp:spike:{brand_id}", 3600):
            cache.publish({"type": "brand.spike", "brand_id": brand_id, "count": count})

    checked = []
    if body.check:
        for item, n, _ in inserted[:MAX_CHECKS]:
            check = await run_check(session, item.url, "hunter", "deep" if body.check_mode == "deep" else "fast", settings,
                                    deep_from_score=body.check_mode == "screen")
            checked.append({"url": item.url, "check_id": check.id, "verdict": check.verdict, "score": check.score})
    return {"received": len(body.entries), "new": len(inserted), "checked": checked}


@router.post("/watchlist/run", description="Queue deep re-checks of due watchlist domains (called by the Hunter ticker).")
async def watchlist_run(session: SessionDep, settings: SettingsDep) -> dict:
    ids = await watchlist.run_due(session, settings)
    return {"queued": len(ids), "check_ids": ids}


class HitBatch(BaseModel):
    channel: str = Field(pattern="^(dns|browser|share)$")
    counts: dict[str, int] = Field(max_length=5000, description="domain -> blocked count since the last call")


@router.post("/hits", description="Block counters from DNS Shield (per domain and channel only, no user data).")
def hits(body: HitBatch, session: SessionDep) -> dict:
    for domain, amount in body.counts.items():
        if amount > 0:
            count_hit(session, domain.lower()[:253], body.channel, min(amount, 1_000_000))
    session.commit()
    return {"domains": len(body.counts)}
