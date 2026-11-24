"""Takedown pack: one zip per recipient covering every domain sent to it in one batch.

    evidence/<domain>.pdf     the evidence record (Arabic and English)
    evidence/<domain>.json    the same record as JSON, with its chain hashes
    screenshots/<domain>.png  the phone screenshot, when there is one
    email.txt                 To, Subject and a bilingual body
    manifest.sha256           `sha256sum -c` format, every file above

The zip is rebuilt on each download and is byte-for-byte reproducible (fixed timestamps, sorted
entries, PDF creation date taken from the record), so its SHA-256 always matches the one stored on
the request. Resident report notes are never included.

Hardening (third-party data reaches this file): a domain that is not a plain host name is refused before any
zip path is built, and every value written into an email line is flattened to one line.
"""
import hashlib
import io
import json
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.defang import defang
from app.evidence import pdf, store
from app.models import Evidence

ZIP_TIME = (2020, 1, 1, 0, 0, 0)
MAX_FIELD = 200
MAX_DOMAIN = 253
DOMAIN_PATTERN = r"^[a-z0-9][a-z0-9.-]*$"


def check_domain(domain: str) -> str:
    """The domain unchanged if it is a plain host name; otherwise ValueError. Used for zip paths."""
    if (not isinstance(domain, str) or len(domain) > MAX_DOMAIN or not re.fullmatch(DOMAIN_PATTERN, domain)
            or ".." in domain):
        raise ValueError(f"Unsafe domain name: {str(domain)[:80]!r}")
    return domain


def one_line(value: object) -> str:
    """The value as one short line for email.txt. Line breaks, control characters and Unicode line
    separators become a space, so third-party data cannot add a header or a line."""
    text = "".join(" " if unicodedata.category(c)[0] == "C" or unicodedata.category(c) in ("Zl", "Zp") else c
                   for c in str(value or "-"))
    return re.sub(r" {2,}", " ", text).strip()[:MAX_FIELD] or "-"


@dataclass
class Item:
    domain: str
    evidence: Evidence
    brand: str | None


def evidence_json(evidence: Evidence) -> bytes:
    record = {"id": evidence.id, "seq": evidence.seq, "check_id": evidence.check_id, "domain": evidence.domain,
              "created_at": evidence.created_at.isoformat(), "prev_hash": evidence.prev_hash, "hash": evidence.hash,
              "payload": evidence.payload}
    return json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True, default=str).encode()


def screenshot(session: Session, evidence: Evidence) -> bytes | None:
    """The phone screenshot: path inside the captures directory and PNG signature checked by the store."""
    return store.screenshot_png(session, evidence.id)


def email(recipient: str, recipient_kind: str, items: list[Item], generated_at: datetime) -> str:
    names = [one_line(defang(item.domain)) for item in items]
    brands = sorted({one_line(item.brand) for item in items if item.brand})
    target = f" impersonating {', '.join(brands)}" if brands else ""
    recipient, recipient_kind = one_line(recipient), one_line(recipient_kind)
    to = recipient if not recipient.startswith("https://") else f"(web form) {recipient}"
    lines = [
        f"To: {to}",
        f"Subject: Phishing takedown request: {len(items)} domain(s){target} / طلب إيقاف مواقع تصيّد",
        "",
        "Hello,",
        "",
        f"The following domain(s) host phishing pages{target} that target residents of the United Arab Emirates.",
        "Each was captured in an isolated browser and reviewed by a police officer before this request.",
        "Please suspend the domain(s) or remove the content. The evidence records, screenshots and a SHA-256",
        "manifest are attached; each record carries a hash chain value that can be verified on request.",
        "",
        *[f"  - {name}  (evidence {one_line(item.evidence.id)})" for name, item in zip(names, items)],
        "",
        "السلام عليكم،",
        "",
        "تستضيف النطاقات المذكورة أعلاه صفحات تصيّد احتيالي تستهدف سكان دولة الإمارات العربية المتحدة.",
        "تم التقاط كل صفحة في متصفح معزول وراجعها ضابط شرطة قبل إرسال هذا الطلب.",
        "نرجو إيقاف النطاقات أو إزالة المحتوى. سجلات الأدلة ولقطات الشاشة وملف التحقق SHA-256 مرفقة.",
        "",
        "Domains are written defanged ([.] instead of .) so that nothing in this message is a live link.",
        f"Prepared {generated_at:%Y-%m-%d %H:%M} UTC for: {recipient_kind}.",
        "",
    ]
    return "\n".join(lines)


def build(session: Session, recipient: str, recipient_kind: str, items: list[Item], generated_at: datetime) -> bytes:
    for item in items:
        check_domain(item.domain)  # before any zip path or file is built
    files: dict[str, bytes] = {}
    for item in sorted(items, key=lambda i: i.domain):
        files[f"evidence/{item.domain}.pdf"] = pdf.render(session, item.evidence)
        files[f"evidence/{item.domain}.json"] = evidence_json(item.evidence)
        image = screenshot(session, item.evidence)
        if image is not None:
            files[f"screenshots/{item.domain}.png"] = image
    files["email.txt"] = email(recipient, recipient_kind, sorted(items, key=lambda i: i.domain), generated_at).encode()
    manifest = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items()))
    files["manifest.sha256"] = manifest.encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name])
    return buffer.getvalue()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
