import uuid
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brands import find_brand, load_brands, safe_action
from app.models import Check, Domain

ALLOWLISTED = {
    "code": "ALLOWLISTED",
    "weight": 0,
    "source": "kartoshka",
    "en": "Official or allowlisted domain",
    "ar": "نطاق رسمي أو مدرج في قائمة النطاقات الموثوقة",
}
BLOCKLISTED = {
    "code": "BLOCKLISTED",
    "weight": 100,
    "source": "kartoshka",
    "en": "Domain is on the confirmed blocklist",
    "ar": "النطاق مدرج في قائمة الحظر المؤكدة",
}


def host_and_parents(url: str) -> list[str]:
    labels = (urlparse(url).hostname or "").split(".")
    return [".".join(labels[i:]) for i in range(len(labels) - 1)] or [".".join(labels)]


def lookup_domain(session: Session, url: str) -> Domain | None:
    candidates = host_and_parents(url)
    rows = session.scalars(select(Domain).where(Domain.domain.in_(candidates))).all()
    return max(rows, key=lambda row: len(row.domain), default=None)


def run_check(session: Session, url: str, source: str, mode: str, data_dir: str) -> Check:
    """Look the URL up in the domains table and store the resulting check row."""
    match = lookup_domain(session, url)
    check = Check(
        id=f"c_{uuid.uuid4().hex}",
        url=url,
        source=source,
        mode=mode,
        verdict="pending",
        score=0,
        stage="fast",
        reasons=[],
    )
    if match and match.status == "confirmed":
        brand = find_brand(load_brands(data_dir), match.brand_id)
        check.verdict, check.score, check.reasons = "block", 100, [BLOCKLISTED]
        if brand:
            check.brand, check.safe_action = brand["names"][0], safe_action(brand, url)
    elif match:
        check.verdict, check.reasons = "allow", [ALLOWLISTED]
    session.add(check)
    session.commit()
    return check
