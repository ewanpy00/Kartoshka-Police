"""Resident reports (ARCHITECTURE.md 3.1, "My reports"): a random id and a secret token, no identity.

Timeline: Sent -> Analysed -> In police review -> Confirmed / Rejected -> Taken down -> Impact.
"""
import hashlib
import hmac
import secrets
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.fast import intel
from app.models import Check, Domain, Evidence, Hit, Report, Review, TakedownRequest, Watchlist
from app.review import RESIDENT_TEXT

VERDICT_TEXT = {
    "allow": ("No scam signs found automatically", "لم يُعثر تلقائيًا على علامات احتيال"),
    "warn": ("Suspicious: sent to the police for review", "مشبوه: أُرسل إلى الشرطة للمراجعة"),
    "block": ("Likely scam: sent to the police for review", "احتيال محتمل: أُرسل إلى الشرطة للمراجعة"),
    "pending": ("Being analysed", "قيد التحليل"),
}


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create(session: Session, check: Check, note: str, push_token: str | None) -> tuple[Report, str]:
    token = secrets.token_urlsafe(24)
    report = Report(id=f"r_{secrets.token_hex(10)}", token_hash=token_hash(token), check_id=check.id, url=check.url,
                    domain=intel.site_key(session, check.host or "", check.domain), note=note or None,
                    push_token=push_token)
    session.add(report)
    return report, token


def authorised(report: Report | None, token: str) -> bool:
    return report is not None and bool(token) and hmac.compare_digest(report.token_hash, token_hash(token))


def step(step_id: str, done: bool, at: datetime | None, en: str, ar: str) -> dict:
    return {"id": step_id, "done": done, "at": at.isoformat() if at else None, "en": en, "ar": ar}


def timeline(session: Session, report: Report) -> dict:
    check = session.get(Check, report.check_id)
    site = report.domain
    analysed = check.stage in ("deep", "officer") or check.deep_status in (None, "done", "failed")
    steps = [step("sent", True, report.created_at, "Report sent", "تم إرسال البلاغ")]
    en, ar = VERDICT_TEXT.get(check.verdict, VERDICT_TEXT["pending"])
    steps.append(step("analysed", analysed, check.updated_at if analysed else None, en, ar))

    latest = session.execute(
        select(Review).join(Evidence, Evidence.id == Review.evidence_id).join(Check, Check.id == Evidence.check_id)
        .where((Check.domain == site) | (Check.host == site)).order_by(Review.reviewed_at.desc()).limit(1)
    ).scalar()
    domain = session.get(Domain, site) if site else None
    in_review = analysed and check.verdict in ("warn", "block") and latest is None
    steps.append(step("in_review", in_review or latest is not None, None, "In police review", "قيد مراجعة الشرطة"))

    final = None
    if latest is not None:
        key = "confirm" if latest.decision == "confirm" else (latest.reason or "insufficient_evidence")
        en, ar = RESIDENT_TEXT[key]
        final = "confirmed" if latest.decision == "confirm" else "rejected"
        steps.append(step(final, True, latest.reviewed_at, en, ar))
    elif domain is not None and domain.status == "confirmed":
        final = "confirmed"
        en, ar = RESIDENT_TEXT["confirm"]
        steps.append(step("confirmed", True, domain.updated_at, en, ar))

    if final == "confirmed":
        closed = session.scalar(select(TakedownRequest).where(TakedownRequest.domain == site, TakedownRequest.status == "closed")
                                .order_by(TakedownRequest.offline_at.desc()).limit(1))
        watched = session.get(Watchlist, site)
        offline_at = closed.offline_at if closed else (watched.offline_since if watched and watched.last_status == "unreachable" else None)
        steps.append(step("taken_down", offline_at is not None, offline_at, "Site taken down", "تم إيقاف الموقع"))
        if offline_at is not None:
            final = "taken_down"

    blocked = session.scalar(select(func.coalesce(func.sum(Hit.count), 0)).where(Hit.domain.in_([site, check.domain]))) or 0
    times = "time" if blocked == 1 else "times"
    steps.append(step("impact", blocked > 0, None, f"Blocked {blocked} {times} for other residents",
                      f"تم حظره {blocked} مرة لحماية سكان آخرين"))
    status = final or ("in_review" if in_review else "analysed" if analysed else "sent")
    if final in ("rejected", "taken_down") and report.push_token:
        report.push_token = None  # the push token is kept only until the final status
    return {"report_id": report.id, "url": report.url, "status": status, "verdict": check.verdict,
            "brand": check.brand, "created_at": report.created_at.isoformat(), "blocked_count": int(blocked),
            "steps": steps, "checked_at": datetime.now(UTC).isoformat()}
