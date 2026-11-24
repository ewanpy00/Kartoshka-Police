from io import BytesIO

from PIL import Image

from app.evidence.store import append_evidence
from app.models import Check


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (4, 4), "red").save(buffer, "PNG")
    return buffer.getvalue()


def make_payload(title: str = "Pay your fine", text: str = "Enter your card") -> dict:
    return {
        "schema": 1,
        "identity": {
            "url": "https://tamm-pay.xyz/login",
            "final_url": "https://tamm-pay.xyz/login",
            "domain": "tamm-pay.xyz",
            "captured_at": "2026-11-24T10:00:00+00:00",
        },
        "capture": {"title": title, "text": text, "forms": [], "screenshot": None},
        "risk": {
            "score": 85,
            "verdict": "block",
            "credential_form": True,
            "reasons": [{"code": "brand", "weight": 40, "source": "deep", "en": "Brand lookalike", "ar": "تقليد علامة"}],
        },
        "infrastructure": {"rdap_status": "ok", "registrar": "Example Registrar", "name_servers": ["ns1.tamm-pay.xyz"]},
        "scam": {"brand": "tamm", "phones": ["+971500000000"], "whatsapp": [], "payment_hosts": []},
    }


def add_record(session, name: str, payload: dict | None = None, screenshot_file: str | None = None, **kwargs):
    check = Check(
        id=name, url="https://tamm-pay.xyz/", source="test", mode="deep", verdict="block", score=85, stage="deep", reasons=[]
    )
    session.add(check)
    session.flush()
    return append_evidence(session, check.id, payload or make_payload(), screenshot_file, **kwargs)
