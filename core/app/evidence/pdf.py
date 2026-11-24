"""Evidence record as a PDF for officers, courts and takedown packs (ARCHITECTURE.md 1.5).

Arabic is shaped with HarfBuzz (fpdf2 text shaping) in DejaVu Sans. Domains and URLs are defanged so
nothing in the document is a live link.
"""
from pathlib import Path

from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.defang import defang
from app.evidence.store import row_hash
from app.models import Artifact, Evidence, Review

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
GREY = (110, 110, 110)


class EvidencePDF(FPDF):
    def __init__(self, evidence_id: str):
        super().__init__(format="A4")
        self.evidence_id = evidence_id
        self.add_font("DejaVu", "", str(FONT_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
        self.add_font("Mono", "", str(FONT_DIR / "DejaVuSansMono.ttf"))
        self.set_text_shaping(True)
        self.set_auto_page_break(True, margin=15)
        self.set_margins(15, 15, 15)

    def header(self) -> None:
        self.set_font("DejaVu", "B", 13)
        self.cell(0, 8, "Kartoshka-Police · Evidence record · سجل الأدلة", new_x="LMARGIN", new_y="NEXT")
        self.set_font("DejaVu", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 5, self.evidence_id, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("DejaVu", "", 7)
        self.set_text_color(*GREY)
        self.cell(0, 5, f"Page {self.page_no()} · integrity: hash = SHA-256(prev_hash + canonical JSON of the payload)", align="C")

    def section(self, title: str) -> None:
        self.ln(2)
        self.set_font("DejaVu", "B", 10)
        self.set_fill_color(235, 238, 242)
        self.cell(0, 7, title, fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_font("DejaVu", "", 9)

    def row(self, label: str, value, mono: bool = False) -> None:
        if value in (None, "", [], {}):
            return
        text = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
        self.set_font("DejaVu", "B", 8)
        self.set_x(self.l_margin)
        self.cell(42, 5, label)
        self.set_font("Mono" if mono else "DejaVu", "", 8)
        self.multi_cell(0, 5, text[:2000], new_x="LMARGIN", new_y="NEXT")


def render(session: Session, evidence: Evidence) -> bytes:
    p = evidence.payload
    page = p.get("page") or {}
    infra = p.get("infra") or {}
    registration = infra.get("rdap") or {}
    pdf = EvidencePDF(evidence.id)
    pdf.set_creation_date(evidence.created_at)  # the same record always renders to the same bytes (takedown packs)
    pdf.add_page()

    pdf.section("Identity")
    pdf.row("URL", defang(p.get("url")))
    pdf.row("Final URL", defang(p.get("final_url")))
    pdf.row("Redirect chain", [defang(u) for u in p.get("chain") or []])
    pdf.row("Domain", defang(p.get("domain")))
    pdf.row("Discovered via", p.get("discovered_via"))
    pdf.row("Captured at (UTC)", p.get("captured_at"))
    pdf.row("Sandbox", (p.get("sandbox") or {}).get("profile"))

    pdf.section(f"Verdict: {p.get('verdict')} · score {p.get('score')} · {p.get('brand') or 'no brand'}")
    for item in p.get("reasons") or []:
        weight = f"+{item['weight']}" if item.get("weight") else ""
        pdf.set_font("DejaVu", "B", 8)
        pdf.cell(42, 5, f"{item['code']} {weight}")
        pdf.set_font("DejaVu", "", 8)
        pdf.multi_cell(0, 5, item.get("en", ""), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(pdf.l_margin + 42)
        pdf.multi_cell(0, 5, item.get("ar", ""), align="R", new_x="LMARGIN", new_y="NEXT")
    for item in p.get("sources") or []:
        pdf.row(f"source: {item['id']}", f"{item['status']} {item.get('detail') or ''}".strip())

    pdf.section("Page")
    pdf.row("Title", page.get("title"))
    pdf.row("HTTP status", page.get("status"))
    pdf.row("Asks for", page.get("asks_for"))
    pdf.row("Phone / WhatsApp", page.get("phones"))
    pdf.row("Payment endpoints", [defang(h) for h in page.get("payment_hosts") or []])
    pdf.row("Server IP", page.get("server_ip"))
    tls = page.get("tls") or {}
    pdf.row("TLS certificate", f"{tls.get('subjectName')} by {tls.get('issuer')}" if tls else None)
    cloaking = page.get("cloaking")
    pdf.row("Cloaking", f"{cloaking.get('kind')}" if cloaking else None)
    excerpt = (page.get("text_excerpt") or "")[:600]
    pdf.row("Text (excerpt)", excerpt.replace("\n", " "))

    pdf.section("Infrastructure")
    pdf.row("A records", infra.get("a"))
    pdf.row("Name servers", infra.get("ns"))
    pdf.row("ASN", [f"{ip}: AS{info.get('asn')} {info.get('name', '')}" for ip, info in (infra.get("asn") or {}).items()])
    pdf.row("Registrar", registration.get("registrar"))
    pdf.row("Registered", registration.get("registered"))
    pdf.row("Abuse contacts", registration.get("abuse_emails"))
    pdf.row("First certificate", (infra.get("ct") or {}).get("first_seen"))

    artifacts = session.scalars(select(Artifact).where(Artifact.evidence_id == evidence.id)).all()
    shot = next((a for a in artifacts if a.kind == "screenshot"), None)
    if shot is not None:
        path = Path(shot.path)
        if path.is_file() and path.resolve().is_relative_to(Path(get_settings().captures_dir).resolve()):
            pdf.section("Screenshot (Arabic phone profile)")
            pdf.image(str(path), w=55)

    pdf.section("Artifacts (SHA-256)")
    for artifact in artifacts:
        pdf.row(artifact.kind, artifact.sha256, mono=True)

    reviews = session.scalars(select(Review).where(Review.evidence_id == evidence.id).order_by(Review.reviewed_at)).all()
    if reviews:
        pdf.section("Officer review")
        for item in reviews:
            pdf.row(item.reviewed_at.isoformat(timespec="seconds"), f"{item.decision} by {item.reviewer}"
                    + (f" ({item.reason})" if item.reason else ""))

    pdf.section("Integrity")
    pdf.row("Sequence", evidence.seq)
    pdf.row("Previous hash", evidence.prev_hash or "(first record)", mono=True)
    pdf.row("Record hash", evidence.hash, mono=True)
    pdf.row("Recomputed", "matches" if row_hash(evidence.prev_hash, evidence.payload) == evidence.hash else "DOES NOT MATCH")
    return bytes(pdf.output())
