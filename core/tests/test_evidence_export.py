"""Evidence PDF: Arabic font embedded and shaped, defanged and link-free, fetches nothing, screenshot only from captures."""
import io
import socket

import pytest
from factories import make_check

from app.config import Settings
from app.evidence import pdf, store
from app.models import Artifact


def png_bytes() -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buffer, "PNG")
    return buffer.getvalue()


PAYLOAD = {
    "url": "https://tamm-pay.xyz/login", "final_url": "https://tamm-pay.xyz/login", "domain": "tamm-pay.xyz",
    "verdict": "block", "score": 92, "brand": "TAMM",
    "reasons": [
        {"code": "LOOKALIKE", "weight": 40, "en": "Imitates TAMM", "ar": "النطاق يقلّد موقع تم الرسمي"},
        {"code": "CREDENTIAL_FORM", "weight": 25, "en": "Asks for card", "ar": "الصفحة تطلب رقم البطاقة"},
        {"code": "NEW_DOMAIN", "weight": 15, "en": "Registered 3 days ago", "ar": "تم تسجيل النطاق قبل 3 أيام في tamm-pay[.]xyz"},
    ],
    "page": {"title": "تم - الدفع tamm-pay[.]xyz 2026", "payment_hosts": ["pay.tamm-pay.xyz"]},
}


def record(session, shot=None):
    check = make_check(session, "tamm-pay.xyz", 92)
    evidence = store.append(session, check.id, check.domain, PAYLOAD)
    if shot is not None:
        session.add(Artifact(evidence_id=evidence.id, kind="screenshot", sha256="0" * 64, path=str(shot)))
        session.flush()
    return evidence


@pytest.fixture
def captures(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "get_settings", lambda: Settings(captures_dir=str(tmp_path)))
    return tmp_path


def test_arabic_reasons_use_an_arabic_font(session):
    data = pdf.render(session, record(session))
    assert b"NotoNaskhArabic" in data or b"NotoSansArabic" in data
    assert pdf.has_arabic("النطاق") and not pdf.has_arabic("tamm-pay[.]xyz")


def test_plus_in_an_arabic_line_stays_before_its_number():
    assert pdf.ltr_numbers("اتصل على +971500000000") == "اتصل على ‎+971500000000"
    assert pdf.ltr_numbers("call +971500000000") == "call +971500000000"


def test_same_record_renders_to_the_same_bytes(session):
    evidence = record(session)
    assert pdf.render(session, evidence) == pdf.render(session, evidence)


def test_no_links_and_defanged_domains(session, monkeypatch):
    printed = []
    for name in ("cell", "multi_cell"):
        original = getattr(pdf.EvidencePDF, name)

        def spy(self, *args, _original=original, **kwargs):
            printed.append(args[2] if len(args) > 2 else kwargs.get("text", kwargs.get("txt", "")))
            return _original(self, *args, **kwargs)

        monkeypatch.setattr(pdf.EvidencePDF, name, spy)
    data = pdf.render(session, record(session))
    assert b"/Annots" not in data and b"/URI" not in data
    text = "\n".join(str(item) for item in printed)
    assert "hxxps://tamm-pay[.]xyz/login" in text and "pay[.]tamm-pay[.]xyz" in text
    assert "tamm-pay.xyz" not in text.replace("tamm-pay[.]xyz", "")


def test_rendering_opens_no_connection(session, captures, monkeypatch):
    (captures / "shot.png").write_bytes(png_bytes())
    evidence = record(session, captures / "shot.png")

    def refuse(*args, **kwargs):
        raise AssertionError("PDF rendering must not touch the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    assert pdf.render(session, evidence).startswith(b"%PDF")


def has_image(data: bytes) -> bool:
    return b"/Subtype /Image" in data


def test_screenshot_is_embedded_only_from_inside_captures(session, captures, tmp_path_factory):
    (captures / "shot.png").write_bytes(png_bytes())
    assert has_image(pdf.render(session, record(session, captures / "shot.png")))
    outside = tmp_path_factory.mktemp("outside") / "shot.png"
    outside.write_bytes(png_bytes())
    assert not has_image(pdf.render(session, record(session, outside)))
    (captures / "fake.png").write_text("not a png")
    assert not has_image(pdf.render(session, record(session, captures / "fake.png")))
