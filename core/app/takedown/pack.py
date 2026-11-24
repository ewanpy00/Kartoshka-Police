"""Takedown pack: one zip per recipient covering every domain sent to it in one batch.

    evidence/<domain>.pdf     the evidence record (Arabic and English)
    evidence/<domain>.json    the same record as JSON, with its chain hashes
    screenshots/<domain>.png  the phone screenshot, when there is one
    email.txt                 To, Subject and a bilingual body
    manifest.sha256           `sha256sum -c` format, every file above

The zip is rebuilt on each download and is byte-for-byte reproducible (fixed timestamps, sorted
entries, PDF creation date taken from the record), so its SHA-256 always matches the one stored on
the request. Resident report notes are never included.
"""
import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.defang import defang
from app.evidence import pdf
from app.models import Artifact, Evidence

ZIP_TIME = (2020, 1, 1, 0, 0, 0)


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
    artifact = session.scalar(select(Artifact).where(Artifact.evidence_id == evidence.id, Artifact.kind == "screenshot"))
    if artifact is None:
        return None
    root = Path(get_settings().captures_dir).resolve()
    path = Path(artifact.path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return None
    return path.read_bytes()


def email(recipient: str, recipient_kind: str, items: list[Item], generated_at: datetime) -> str:
    names = [defang(item.domain) for item in items]
    brands = sorted({item.brand for item in items if item.brand})
    target = f" impersonating {', '.join(brands)}" if brands else ""
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
        *[f"  - {name}  (evidence {item.evidence.id})" for name, item in zip(names, items)],
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
