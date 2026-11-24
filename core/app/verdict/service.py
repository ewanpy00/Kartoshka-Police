"""Create, store and publish checks. Shared by every route that checks a URL."""
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import cache, queue
from app.brands import display_name
from app.config import Settings
from app.fast.score import Assessment, assess, cache_key
from app.models import Check, Hit, Verdict
from app.verdict.bands import band, needs_deep, source, total

BLOCKLIST_EVIDENCE_HOURS = 30 * 24
DEEP_SOURCES = ("hunter", "user_report", "preview", "pivot", "watchlist")
BLOCK_CHANNELS = {"browser": "browser", "gatekeeper": "browser", "share": "share", "dns": "dns", "sms": "share"}


def new_check_id() -> str:
    return f"c_{uuid.uuid4().hex}"


def recent_deep(session: Session, host: str, hours: int) -> Check | None:
    """A finished deep analysis of the same host, reused instead of running the sandbox again."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    return session.scalar(
        select(Check)
        .where(Check.host == host, Check.stage.in_(("deep", "officer")), Check.deep_status == "done", Check.created_at >= since)
        .order_by(Check.updated_at.desc())
        .limit(1)
    )


def count_hit(session: Session, domain: str, channel: str, amount: int = 1) -> None:
    statement = insert(Hit).values(domain=domain, channel=channel, count=amount)
    session.execute(statement.on_conflict_do_update(
        index_elements=[Hit.domain, Hit.channel], set_={"count": Hit.count + amount, "updated_at": datetime.now(UTC)}
    ))


def check_from(assessment: Assessment, url: str, source_name: str, mode: str) -> Check:
    n = assessment.n
    return Check(
        id=new_check_id(),
        url=url,
        final_url=n.final if n.final != n.url else None,
        host=n.host,
        domain=n.domain,
        source=source_name,
        mode=mode,
        verdict=assessment.verdict,
        score=assessment.score,
        stage="fast",
        brand=display_name(assessment.brand) if assessment.brand else None,
        brand_id=assessment.brand["id"] if assessment.brand else None,
        safe_action=assessment.safe_action,
        reasons=assessment.reasons,
        sources=assessment.sources,
        features=assessment.features,
        chain=n.chain,
    )


def wants_deep(check: Check, mode: str, source_name: str, decided_by: str) -> bool:
    if decided_by in ("allowlist", "blocklist"):
        return False
    return mode == "deep" or source_name in DEEP_SOURCES or needs_deep(check.score)


async def run_check(
    session: Session,
    url: str,
    source_name: str,
    mode: str,
    settings: Settings,
    budget_ms: int | None = None,
    text: str = "",
    enqueue: bool = True,
    deep_from_score: bool = False,
    force_deep: bool = False,
    extra_reasons: list[dict] | None = None,
) -> Check:
    assessment = await assess(session, url, settings, budget_ms, text)
    check = check_from(assessment, url, source_name, mode)
    if extra_reasons and assessment.decided_by == "score":
        check.reasons = check.reasons + extra_reasons
        check.score = total(check.reasons)
        check.verdict = band(check.score)

    reused = None
    if assessment.decided_by not in ("allowlist", "blocklist"):
        reused = recent_deep(session, assessment.n.host, settings.deep_reuse_hours)
    if reused is not None and reused.score >= check.score and not force_deep:
        check.verdict, check.score, check.stage = reused.verdict, reused.score, reused.stage
        check.reasons, check.sources, check.preview = reused.reasons, reused.sources, reused.preview
        check.evidence_id, check.campaign_id, check.deep_status = reused.evidence_id, reused.campaign_id, "done"
        check.brand, check.brand_id = reused.brand or check.brand, reused.brand_id or check.brand_id
        check.safe_action = reused.safe_action or check.safe_action
    elif assessment.decided_by == "blocklist" and not force_deep and (
            prior := recent_deep(session, assessment.n.host, BLOCKLIST_EVIDENCE_HOURS)) is not None:
        # A police-list hit needs no new sandbox run, but the resident still gets the safe preview and the
        # evidence behind the block. The verdict and reasons stay the list's.
        check.preview, check.evidence_id, check.campaign_id = prior.preview, prior.evidence_id, prior.campaign_id
    elif enqueue and (force_deep or (needs_deep(check.score) and assessment.decided_by not in ("allowlist", "blocklist")
                                     if deep_from_score else wants_deep(check, mode, source_name, assessment.decided_by))):
        check.deep_status = "queued"
        check.sources = [
            source(entry["id"], "unknown", "running") if entry["id"] in ("sandbox", "ai") else entry
            for entry in check.sources
        ]

    session.add(check)
    session.flush()
    session.add(Verdict(check_id=check.id, verdict=check.verdict, score=check.score, stage=check.stage, reasons=check.reasons))
    channel = BLOCK_CHANNELS.get(source_name)
    if channel and check.verdict == "block" and check.domain:
        count_hit(session, check.domain, channel)
    session.commit()

    if assessment.decided_by == "score" and check.deep_status != "done":
        ttl = 30 if assessment.timed_out else settings.verdict_cache_ttl_s
        await cache.set_json(cache_key(assessment.n.final), assessment.cacheable(), ttl)
    if check.deep_status == "queued":
        if queue.claim_deep(check.host or "") or force_deep:
            queue.enqueue_deep_check(check.id)
        else:
            check.deep_status = "joined"
            session.commit()
    publish_verdict(check)
    return check


def publish_verdict(check: Check) -> None:
    """`check.verdict` for the console live feed, whenever a check reaches warn or block (fast or deep)."""
    if check.verdict not in ("warn", "block"):
        return
    cache.publish({
        "type": "check.verdict", "check_id": check.id, "domain": check.domain, "host": check.host,
        "verdict": check.verdict, "score": check.score, "stage": check.stage, "source": check.source,
        "brand": check.brand, "at": datetime.now(UTC).isoformat(),
    })
