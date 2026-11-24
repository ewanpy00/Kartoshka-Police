"""Resident screens (ARCHITECTURE.md 3.1): reports, safe preview, scam radar, pasted SMS.

Residents never see reason weights, Hunter internals or other people's reports. Every route is
rate-limited per device (`X-Device-Id`, a random value the app generates; not an identity).
"""
import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app import cache, radar, reports
from app.ai import provider, text_classifier
from app.api.check import shape
from app.auth import address_limit
from app.deps import HOUR, SessionDep, SettingsDep, limit
from app.fast import sms
from app.models import Artifact, Report
from app.schemas import ReportRequest, ReportResponse, Verdict, require_http_url
from app.verdict.reasons import reason
from app.verdict.service import run_check

router = APIRouter()
MINUTE = 60
RADAR_KEY = "kp:radar"
RADAR_TTL_S = 60


@router.post("/report", response_model=ReportResponse, status_code=202,
             description="Report a link. Returns a report id and a secret token; keep the token on the device.")
async def report(body: ReportRequest, request: Request, session: SessionDep, settings: SettingsDep) -> ReportResponse:
    address_limit(request, settings, "report", settings.report_ip_rate_per_hour, HOUR)
    limit(request, "report", settings.report_rate_per_hour)
    check = await run_check(session, body.url, "user_report", "deep", settings)
    row, token = reports.create(session, check, body.note, body.push_token)
    session.commit()
    return ReportResponse(check_id=check.id, status="received", report_id=row.id, token=token)


@router.get("/reports/{report_id}", description="Report timeline. Send the report token in `X-Report-Token`.")
def report_status(report_id: str, request: Request, session: SessionDep, settings: SettingsDep,
                  x_report_token: Annotated[str, Header()] = "") -> dict:
    address_limit(request, settings, "read", settings.read_rate_per_min, MINUTE)
    row = session.get(Report, report_id)
    if not reports.authorised(row, x_report_token):
        raise HTTPException(404, "Unknown report")
    body = reports.timeline(session, row)
    session.commit()
    return body


class PreviewRequest(BaseModel):
    url: str = Field(max_length=4096)
    _url = field_validator("url")(require_http_url)


@router.post("/preview", response_model=Verdict,
             description="Queue a safe preview (a sandbox screenshot) for a link. Poll `GET /v1/check/{id}?view=resident`.")
async def preview(body: PreviewRequest, request: Request, session: SessionDep, settings: SettingsDep):
    address_limit(request, settings, "preview", settings.preview_ip_rate_per_hour, HOUR)
    limit(request, "preview", settings.preview_rate_per_hour)
    check = await run_check(session, body.url, "preview", "deep", settings)
    return shape(check, resident=True)


@router.get("/preview/{evidence_id}.png", response_class=FileResponse,
            description="The phone screenshot behind a link: an image only, nothing on it is clickable.")
def preview_image(evidence_id: str, request: Request, session: SessionDep, settings: SettingsDep) -> FileResponse:
    address_limit(request, settings, "read", settings.read_rate_per_min, MINUTE)
    limit(request, "preview_image", 120)
    artifact = session.scalar(select(Artifact).where(Artifact.evidence_id == evidence_id, Artifact.kind == "screenshot"))
    root = Path(settings.captures_dir).resolve()
    path = Path(artifact.path).resolve() if artifact else None
    if path is None or not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, "No preview for this evidence")
    return FileResponse(path, media_type="image/png", headers={
        "Cache-Control": "private, max-age=3600", "Content-Security-Policy": "default-src 'none'",
        "X-Content-Type-Options": "nosniff", "Content-Disposition": "inline",
    })


@router.get("/radar", description="What is active now in the UAE, grouped by brand. Aggregates only; cached for a minute.")
async def scam_radar(request: Request, session: SessionDep, settings: SettingsDep) -> dict:
    address_limit(request, settings, "read", settings.read_rate_per_min, MINUTE)
    cached = await cache.get_json(RADAR_KEY)
    if cached is not None:
        return cached
    body = radar.build(session, settings.data_dir)
    await cache.set_json(RADAR_KEY, body, RADAR_TTL_S)
    return body


class SmsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/sms", description="Paste an SMS: every link in it is checked (up to five), and the text is read for scam stories.")
async def paste_sms(body: SmsRequest, request: Request, session: SessionDep, settings: SettingsDep) -> dict:
    address_limit(request, settings, "sms", settings.sms_ip_rate_per_hour, HOUR)
    limit(request, "sms", 60)
    reading = sms.classify(body.text)
    extra = []
    if reading["category"] and (reading["urgent"] or reading["links"]):
        extra = [reason("SMS_SCAM_TEXT", category=reading["category_en"], category_ar=reading["category_ar"])]
    ai_reading = None
    if settings.ai_enabled:
        try:
            ai_reading = await asyncio.to_thread(text_classifier.classify, body.text)
        except provider.AIUnavailable:
            ai_reading = None
    if ai_reading and ai_reading["reasons_en"]:
        extra.append(reason("AI_ASSESSMENT", weight=0, text_en=" ".join(ai_reading["reasons_en"]),
                            text_ar=" ".join(ai_reading["reasons_ar"]) or " ".join(ai_reading["reasons_en"])))
    checks = []
    for url in reading["links"]:
        check = await run_check(session, url, "sms", "fast", settings, text=body.text, extra_reasons=extra)
        checks.append(shape(check, resident=True))
    text = {key: reading[key] for key in ("category", "category_en", "category_ar", "urgent")}
    text["by"] = "rules"
    if ai_reading:
        text.update({"by": "rules+ai", "ai": {key: ai_reading[key] for key in (
            "category", "claimed_sender", "asks_to", "urgency", "scam_likelihood", "reasons_en", "reasons_ar")}})
    return {"links": checks, "text": text, "found_links": len(reading["links"])}
