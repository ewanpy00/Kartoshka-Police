import csv
import io
from datetime import datetime
from typing import Annotated

import phonenumbers
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.cases import collect
from app.brands import load_brands
from app.config import Settings, get_settings
from app.csvsafe import cell
from app.db import get_session
from app.models import Domain

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
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


def is_official_host(domain: str, official_domains: list[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in official_domains)


def listed_numbers(session: Session, settings: Settings) -> list[Number]:
    brands = {name.lower(): b for b in load_brands(settings.data_dir) for name in (b["id"], *b["names"])}
    officer_confirmed = set(
        session.scalars(select(Domain.domain).where(Domain.status == "confirmed", Domain.confirmed_by == "officer"))
    )
    found: dict[tuple[str, str, str], Number] = {}
    for case in collect(session):
        evidence, domain = case.evidence, case.domain
        if evidence is None or case.check.verdict not in ("warn", "block"):
            continue
        scam = evidence.payload.get("scam") or {}
        brand = brands.get((scam.get("brand") or "").lower())
        if brand is None or is_official_host(domain, brand["official_domains"]):
            continue
        official = {e164(p) for p in brand.get("official_phones", [])}
        for raw in [*scam.get("phones", []), *scam.get("whatsapp", [])]:
            phone = e164(raw)
            if phone is None or phone in official:
                continue
            found.setdefault(
                (phone, brand["id"], domain),
                Number(
                    phone=phone, brand=scam["brand"], source="page", domain=domain,
                    evidence_id=evidence.id, first_seen=evidence.created_at,
                    confirmed=domain in officer_confirmed,
                ),
            )
    return list(found.values())


@router.get("/helplines", response_model=NumberList)
def helplines(session: SessionDep, settings: SettingsDep) -> NumberList:
    return NumberList(numbers=listed_numbers(session, settings))


@router.get("/helplines.csv")
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
