"""Evidence record as a PDF for officers, courts and takedown packs (ARCHITECTURE.md 1.5).

Arabic is shaped with HarfBuzz (fpdf2 text shaping) and laid out right to left with fpdf2's bidi
algorithm, in Noto Naskh Arabic (package fonts-noto-core); Latin runs, digits and defanged domains inside
an Arabic line stay left to right. Latin text is DejaVu Sans. Domains and URLs are defanged so nothing
in the document is a live link. fpdf2 fetches nothing: the only image is the local screenshot file, and
only when its path resolves inside the captures directory and it begins with the PNG signature.
"""
import re
from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.defang import defang
from app.evidence.store import row_hash, screenshot_png
from app.models import Artifact, Evidence, Review

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
NOTO_DIR = Path("/usr/share/fonts/truetype/noto")
ARABIC = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]")
GREY = (110, 110, 110)


def has_arabic(text: str) -> bool:
    return bool(ARABIC.search(text))


def ltr_numbers(text: str) -> str:
    """In an Arabic line a leading + would sit after its number; a left-to-right mark keeps `+97150...` in order."""
    return re.sub(r"(?<![\w\u200e])\+(?=\d)", "\u200e+", text) if has_arabic(text) else text


def arabic_font(style: str) -> Path:
    """Noto Naskh Arabic, else Noto Sans Arabic, in the requested style."""
    suffix = "Bold" if style == "B" else "Regular"
    for family in ("NotoNaskhArabic", "NotoSansArabic"):
        path = NOTO_DIR / f"{family}-{suffix}.ttf"
        if path.is_file():
            return path
    raise FileNotFoundError(f"No Arabic font in {NOTO_DIR}; install fonts-noto-core")


class EvidencePDF(FPDF):
    def __init__(self, evidence_id: str):
        super().__init__(format="A4")
        self.evidence_id = evidence_id
        self.add_font("DejaVu", "", str(FONT_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
        self.add_font("Mono", "", str(FONT_DIR / "DejaVuSansMono.ttf"))
        self.add_font("Arabic", "", str(arabic_font("")))
        self.add_font("Arabic", "B", str(arabic_font("B")))
        # Glyphs the Arabic face lacks (most Latin) come from DejaVu, run by run.
        self.set_fallback_fonts(["DejaVu"])
        self.set_text_shaping(True)
        self.set_auto_page_break(True, margin=15)
        self.set_margins(15, 15, 15)

    def face(self, text: str, style: str = "", size: float = 8, mono: bool = False) -> bool:
        """Pick the font and text direction for this text. Returns True for an Arabic line (right to left,
        right-aligned); Latin runs and digits inside it still read left to right through the bidi pass."""
        arabic = has_arabic(text)
        self.set_text_shaping(True, direction="rtl" if arabic else None)
        if arabic:
            self.set_font("Arabic", style, size + 1)
        else:
            self.set_font("Mono" if mono else "DejaVu", style, size)
        return arabic

    def header(self) -> None:
        self.set_text_color(0, 0, 0)
        self.face("Kartoshka-Police · Evidence record", "B", 13)
        self.cell(110, 8, "Kartoshka-Police · Evidence record")
        self.face("سجل الأدلة", "B", 13)
        self.cell(0, 8, "سجل الأدلة", align="R", new_x="LMARGIN", new_y="NEXT")
        self.face(self.evidence_id, "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 5, self.evidence_id, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-12)
        self.face("Page", "", 7)
        self.set_text_color(*GREY)
        self.cell(0, 5, f"Page {self.page_no()} · integrity: hash = SHA-256(prev_hash + canonical JSON of the payload)", align="C")
        self.set_text_color(0, 0, 0)

    def section(self, title: str) -> None:
        self.ln(2)
        arabic = self.face(title, "B", 10)
        self.set_fill_color(235, 238, 242)
        self.cell(0, 7, title, fill=True, align="R" if arabic else "L", new_x="LMARGIN", new_y="NEXT")

    def row(self, label: str, value, mono: bool = False) -> None:
        if value in (None, "", [], {}):
            return
        text = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
        self.set_x(self.l_margin)
        self.face(label, "B", 8)
        self.cell(42, 5, label)
        arabic = self.face(text, "", 8, mono)
        self.multi_cell(0, 5, ltr_numbers(text[:2000]), align="R" if arabic else "L", new_x="LMARGIN", new_y="NEXT")


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
        pdf.set_x(pdf.l_margin)
        pdf.face("code", "B", 8)
        pdf.cell(42, 5, f"{item['code']} {weight}".strip())
        english = item.get("en") or ""
        pdf.face(english, "", 8)
        pdf.multi_cell(0, 5, english, new_x="LMARGIN", new_y="NEXT")
        arabic = item.get("ar") or ""
        if arabic:  # right to left, right-aligned, under the English line
            pdf.set_x(pdf.l_margin + 42)
            pdf.face(arabic, "", 8)
            pdf.multi_cell(0, 6, ltr_numbers(arabic), align="R", new_x="LMARGIN", new_y="NEXT")
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
        png = screenshot_png(session, evidence.id)  # inside the captures directory, PNG signature checked
        if png is not None:
            pdf.section("Screenshot (Arabic phone profile)")
            pdf.image(BytesIO(png), w=55)

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
