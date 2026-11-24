import uuid
from urllib.parse import urlparse

import idna
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


def encode_label(label: str) -> str:
    try:
        return idna.encode(label).decode("ascii")
    except idna.IDNAError:
        return label


def normalize_host(host: str) -> str:
    """Map a host as browsers do (UTS 46, non-transitional), drop trailing dots and punycode each label.

    A label that fails to encode is kept as given, so one odd label cannot stop its parents from matching.
    It is invalid or non-ASCII, so it cannot equal a seeded label.
    """
    try:
        host = idna.uts46_remap(host, std3_rules=False, transitional=False)
    except idna.IDNAError:
        host = host.lower()
    return ".".join(encode_label(label) for label in host.rstrip(".").split("."))


def host_and_parents(url: str) -> list[str]:
    """The host a browser would visit, then its parent domains. Browsers read a backslash as a slash."""
    parsed = urlparse(url.strip().replace("\\", "/"))
    labels = normalize_host(parsed.hostname or "").split(".")
    return [".".join(labels[i:]) for i in range(len(labels) - 1)] or [".".join(labels)]


def domain_of(url: str) -> str:
    """The case key for a URL: its normalised host without a leading `www.`."""
    return host_and_parents(url)[0].removeprefix("www.")


def lookup_domain(session: Session, url: str) -> Domain | None:
    """Official and confirmed entries match the host or a parent; allowlisted ones only the host or its www form."""
    host, *_ = candidates = host_and_parents(url)
    rows = session.scalars(select(Domain).where(Domain.domain.in_(candidates))).all()
    matches = [row for row in rows if row.status != "allowlisted" or host in (row.domain, f"www.{row.domain}")]
    return max(matches, key=lambda row: (row.status == "confirmed", len(row.domain)), default=None)


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
        domain=domain_of(url),
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
