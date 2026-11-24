"""Fake helplines: the phone numbers scam pages show, from each case's representative evidence (docs/admin-plan.md).

A number is listed when the case's representative check names a brand and its verdict is warn or block. The
brand's own numbers (`app.brands.official_phones()`) and the brand's own hosts are left out. The CSV carries
only the numbers of sites an officer confirmed; every cell goes through `csvsafe.cell`.
"""
import csv
import io
from datetime import UTC, datetime

import phonenumbers
from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import brands as brand_registry
from app.admin import queue
from app.config import Settings
from app.csvsafe import cell
from app.deps import SessionDep, SettingsDep
from app.models import Evidence

router = APIRouter()

COLUMNS = ("phone", "brand", "source", "domain", "evidence_id", "first_seen")


class Number(BaseModel):
    phone: str
    brand: str
    source: str
    domain: str
    evidence_id: str
    first_seen: datetime
    confirmed: bool


class NumberList(BaseModel):
    numbers: list[Number]


def e164(raw: str) -> str | None:
    try:
        return phonenumbers.format_number(phonenumbers.parse(raw, "AE"), phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return None


def official_numbers() -> frozenset[str]:
    """The brands' own numbers, normalised. Empty when `app.brands.official_phones` does not exist (yet)."""
    found = getattr(brand_registry, "official_phones", None)
    return frozenset(filter(None, (e164(p) for p in found()))) if found else frozenset()


def page_numbers(payload: dict) -> list[str]:
    """Phones and WhatsApp numbers the page showed. The deep job writes them under `page`; older records under `scam`."""
    found = []
    for block in (payload.get("page") or {}, payload.get("scam") or {}):
        found += [*(block.get("phones") or []), *(block.get("whatsapp") or [])]
    return found


def listed_numbers(session: Session, settings: Settings) -> list[Number]:
    registry = {name.lower(): b for b in brand_registry.load_brands(settings.data_dir) for name in (b["id"], *b["names"])}
    official = official_numbers()
    found: dict[tuple[str, str], Number] = {}
    for case in queue.collect(session, datetime.now(UTC), window=None).values():
        check = case.latest
        if case.status in queue.HIDDEN or check is None or not check.evidence_id or check.verdict not in queue.FLAGGED:
            continue
        brand = registry.get((check.brand_id or check.brand or "").lower())
        evidence = session.get(Evidence, check.evidence_id)
        if brand is None or evidence is None or brand_registry.is_official(case.site, brand):
            continue
        confirmed = case.status == "confirmed" and case.confirmed_by == "officer"
        for raw in page_numbers(evidence.payload or {}):
            phone = e164(raw)
            if phone is None or phone in official:
                continue
            found.setdefault((phone, case.site), Number(
                phone=phone, brand=check.brand or brand["names"][0], source="page", domain=case.site,
                evidence_id=evidence.id, first_seen=evidence.created_at, confirmed=confirmed))
    return sorted(found.values(), key=lambda n: (n.first_seen, n.phone))


@router.get("/helplines", response_model=NumberList)
def helplines(session: SessionDep, settings: SettingsDep) -> NumberList:
    return NumberList(numbers=listed_numbers(session, settings))


@router.get("/helplines.csv", description="Officer-confirmed fake numbers only, as a download.")
def helplines_csv(session: SessionDep, settings: SettingsDep) -> Response:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(COLUMNS)
    for number in listed_numbers(session, settings):
        if not number.confirmed:
            continue
        row = number.model_dump(mode="json")
        writer.writerow(cell(row[column]) for column in COLUMNS)
    return Response(
        out.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="helplines.csv"'}
    )
