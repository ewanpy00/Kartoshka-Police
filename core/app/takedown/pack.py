import hashlib
import io
import json
import re
import unicodedata
import zipfile

from sqlalchemy.orm import Session

from app.evidence.export import defang, export_json, render_pdf
from app.evidence.store import screenshot_png
from app.models import Evidence

MAX_FIELD = 200
DOMAIN_PATTERN = r"^[a-z0-9][a-z0-9.-]*$"

REQUEST_EN = (
    "Please suspend or take down the domains below. They impersonate a UAE government service "
    "and collect residents' credentials. The attached evidence records are hash-chained; "
    "manifest.sha256 lists the SHA-256 of every file in this pack."
)
REQUEST_AR = (
    "نرجو تعليق النطاقات التالية أو إزالتها. فهي تنتحل صفة خدمة حكومية إماراتية وتجمع بيانات "
    "دخول السكان. سجلات الأدلة المرفقة مترابطة بالتجزئة، ويسرد الملف manifest.sha256 "
    "قيمة SHA-256 لكل ملف في هذه الحزمة."
)


def check_domain(domain: str) -> str:
    if not re.fullmatch(DOMAIN_PATTERN, domain) or ".." in domain:
        raise ValueError(f"Unsafe domain name: {domain[:80]!r}")
    return domain


def one_line(value: object) -> str:
    """The value as one short line for email.txt; third-party data must not be able to add lines."""
    text = "".join(" " if unicodedata.category(c)[0] == "C" or unicodedata.category(c) in ("Zl", "Zp") else c for c in str(value or "-"))
    return re.sub(r" {2,}", " ", text).strip()[:MAX_FIELD]


def email_text(recipient: str, items: list[tuple[str, Evidence]]) -> str:
    lines = []
    for domain, evidence in items:
        infra = evidence.payload.get("infrastructure", {})
        lines.append(
            f"- {one_line(defang(domain))} | IP {one_line(defang(infra.get('ip') or '-'))} | "
            f"registrar {one_line(infra.get('registrar'))} | evidence {one_line(evidence.hash)}"
        )
    domains = "\n".join(lines)
    return (
        f"To: {one_line(recipient)}\n"
        "Subject: Abuse report: phishing domains impersonating a UAE government service / "
        "بلاغ إساءة: نطاقات تصيد تنتحل صفة جهة حكومية إماراتية\n\n"
        f"{REQUEST_EN}\n\nDomains:\n{domains}\n\n---\n\n{REQUEST_AR}\n\nالنطاقات:\n{domains}\n"
    )


def build_zip(session: Session, recipient: str, items: list[tuple[str, Evidence]]) -> bytes:
    """One zip for a recipient: per domain a PDF, the JSON and the screenshot, then email.txt and manifest.sha256."""
    files = {"email.txt": email_text(recipient, items).encode()}
    for domain, evidence in items:
        folder = check_domain(domain)
        files[f"{folder}/evidence.pdf"] = render_pdf(session, evidence.id)
        files[f"{folder}/evidence.json"] = json.dumps(export_json(session, evidence.id), indent=2, ensure_ascii=False).encode()
        png = screenshot_png(evidence)
        if png:
            files[f"{folder}/screenshot.png"] = png
    files["manifest.sha256"] = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return out.getvalue()
