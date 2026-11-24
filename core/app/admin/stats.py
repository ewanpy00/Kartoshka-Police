"""Impact and model-quality numbers for the console (D6 of docs/admin-dashboard.md).

Lead time is measured per officer-confirmed domain that Hunter saw in Certificate Transparency:

    seen        first CT sighting (feed_entries, source ct)
    confirmed   the officer's confirm (audit_log, review.confirm)
    gsb / vt    when Google Safe Browsing or VirusTotal first flagged it, recorded by the takedown
                re-checks and the deep path; None while they have not
    lead        gsb (or vt) minus seen: how much earlier we knew. While a list has not flagged the
                domain, the lead is at least now minus seen and is marked `open`.

Model quality compares what the system said before the officer looked (the `before` of the review's
audit row) with the officer's decision, which is the label the retrain loop (A7) learns from.
"""
import statistics
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.defang import defang
from app.models import AuditLog, Check, Domain, FeedEntry, Hit, ModelState, Report, Review, TakedownRequest

RANGES = {"24h": (timedelta(hours=24), timedelta(hours=1)), "7d": (timedelta(days=7), timedelta(days=1))}
CLEARING = ("legitimate_site", "not_a_scam")


def hours(a: datetime | None, b: datetime | None) -> float | None:
    if a is None or b is None:
        return None
    return round((a - b).total_seconds() / 3600, 1)


def median(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    return round(statistics.median(values), 1) if values else None


def buckets(since: datetime, step: timedelta, now: datetime) -> list[datetime]:
    start = since.replace(minute=0, second=0, microsecond=0)
    if step == timedelta(days=1):
        start = start.replace(hour=0)
    out, t = [], start
    while t <= now:
        out.append(t)
        t += step
    return out


def series(session: Session, column, since: datetime, step: timedelta, now: datetime, *where) -> list[int]:
    unit = "hour" if step == timedelta(hours=1) else "day"
    bucket = func.date_trunc(unit, func.timezone("UTC", column))
    rows = session.execute(select(bucket, func.count()).where(column >= since, *where).group_by(bucket)).all()
    counts = {bucket.replace(tzinfo=UTC): n for bucket, n in rows}
    return [counts.get(t, 0) for t in buckets(since, step, now)]


def lead_times(session: Session, now: datetime) -> list[dict]:
    seen = dict(session.execute(
        select(FeedEntry.domain, func.min(FeedEntry.first_seen)).where(FeedEntry.source == "ct").group_by(FeedEntry.domain)
    ).all())
    if not seen:
        return []
    confirmed_at = dict(session.execute(
        select(AuditLog.target, func.min(AuditLog.created_at))
        .where(AuditLog.action == "review.confirm", AuditLog.target.in_(seen)).group_by(AuditLog.target)
    ).all())
    rows = []
    for domain in session.scalars(select(Domain).where(Domain.domain.in_(seen), Domain.status == "confirmed",
                                                       or_(Domain.confirmed_by == "officer",
                                                           and_(Domain.confirmed_by.is_(None), Domain.source == "officer")))):
        first = seen[domain.domain]
        gsb, vt = domain.gsb_first_hit_at, domain.vt_first_hit_at
        rows.append({
            "domain": domain.domain, "display": defang(domain.domain), "brand_id": domain.brand_id,
            "seen": first.isoformat(), "confirmed": confirmed_at[domain.domain].isoformat() if domain.domain in confirmed_at else None,
            "hours_to_confirm": hours(confirmed_at.get(domain.domain), first),
            "gsb_first_hit": gsb.isoformat() if gsb else None, "vt_first_hit": vt.isoformat() if vt else None,
            "lead_vs_gsb_h": hours(gsb or now, first), "lead_vs_gsb_open": gsb is None,
            "lead_vs_vt_h": hours(vt or now, first), "lead_vs_vt_open": vt is None,
        })
    return sorted(rows, key=lambda r: r["seen"], reverse=True)


def impact(session: Session, range_key: str = "24h", now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    window, step = RANGES[range_key]
    since = now - window
    real = Check.source != "batch"
    verdicts = dict(session.execute(
        select(Check.verdict, func.count()).where(Check.created_at >= since, real).group_by(Check.verdict)).all())
    candidates = dict(session.execute(
        select(FeedEntry.source, func.count()).where(FeedEntry.first_seen >= since).group_by(FeedEntry.source)).all())
    reviews = dict(session.execute(
        select(Review.decision, func.count()).where(Review.reviewed_at >= since).group_by(Review.decision)).all())
    hit_rows = dict(session.execute(
        select(Hit.channel, func.sum(Hit.count)).where(Hit.updated_at >= since).group_by(Hit.channel)).all())
    leads = lead_times(session, now)
    closed = session.execute(select(TakedownRequest.sent_at, TakedownRequest.offline_at).where(
        TakedownRequest.status == "closed", TakedownRequest.offline_at >= since)).all()
    return {
        "range": range_key, "since": since.isoformat(), "now": now.isoformat(),
        "totals": {
            "checks": sum(verdicts.values()), "warn": verdicts.get("warn", 0), "block": verdicts.get("block", 0),
            "candidates": sum(candidates.values()), "candidates_by_source": candidates,
            "reports": session.scalar(select(func.count()).select_from(Report).where(Report.created_at >= since)),
            "confirmed": reviews.get("confirm", 0), "rejected": reviews.get("reject", 0),
            "blocked_hits": {channel: int(total or 0) for channel, total in hit_rows.items()},
            "blocklist_size": session.scalar(select(func.count()).select_from(Domain).where(Domain.status == "confirmed")),
            "taken_down": len(closed),
        },
        "series": {
            "buckets": [t.isoformat() for t in buckets(since, step, now)],
            "checks": series(session, Check.created_at, since, step, now, real, Check.verdict.in_(("warn", "block"))),
            "candidates": series(session, FeedEntry.first_seen, since, step, now),
            "confirmed": series(session, Review.reviewed_at, since, step, now, Review.decision == "confirm"),
        },
        "lead_time": {
            "domains": leads,
            "median_hours_to_confirm": median([r["hours_to_confirm"] for r in leads]),
            "median_lead_vs_gsb_h": median([r["lead_vs_gsb_h"] for r in leads]),
            "median_lead_vs_vt_h": median([r["lead_vs_vt_h"] for r in leads]),
            "flagged_by_gsb_later": sum(1 for r in leads if not r["lead_vs_gsb_open"]),
            "not_flagged_by_gsb_yet": sum(1 for r in leads if r["lead_vs_gsb_open"]),
        },
        "takedown_median_hours": median([hours(off, sent) for sent, off in closed]),
    }


def quality(session: Session, now: datetime | None = None, days: int = 30) -> dict:
    """System verdict before review vs officer decision, per band and per stage; and the URL model's metrics."""
    now = now or datetime.now(UTC)
    rows = session.execute(
        select(AuditLog.action, AuditLog.before, AuditLog.reason)
        .where(AuditLog.action.in_(("review.confirm", "review.reject")), AuditLog.created_at >= now - timedelta(days=days))
    ).all()
    table = {band: {"confirmed": 0, "cleared": 0, "other_reject": 0} for band in ("allow", "warn", "block")}
    for action, before, reason in rows:
        band = (before or {}).get("verdict") or "allow"
        cell = table.setdefault(band, {"confirmed": 0, "cleared": 0, "other_reject": 0})
        if action == "review.confirm":
            cell["confirmed"] += 1
        elif reason in CLEARING:
            cell["cleared"] += 1
        else:
            cell["other_reject"] += 1
    block = table["block"]
    decided_block = block["confirmed"] + block["cleared"]
    warn = table["warn"]
    decided_warn = warn["confirmed"] + warn["cleared"]
    model = session.get(ModelState, "url_model")
    metrics = (model.value or {}).get("metrics") if model else None
    return {
        "days": days, "reviews": len(rows), "by_band": table,
        "block_precision": round(block["confirmed"] / decided_block, 3) if decided_block else None,
        "warn_confirm_rate": round(warn["confirmed"] / decided_warn, 3) if decided_warn else None,
        "false_blocks": block["cleared"],
        "url_model": None if model is None else {"updated_at": model.updated_at.isoformat(), "score": model.score,
                                                 "metrics": metrics},
        "labels_for_retrain": session.scalar(select(func.count()).select_from(Review).where(
            (Review.decision == "confirm") | Review.reason.in_(CLEARING))),
    }
