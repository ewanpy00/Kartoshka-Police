from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import require_write_token
from app.config import Settings, get_settings
from app.db import get_session
from app.models import Evidence

from .export import export_json, render_pdf
from .store import screenshot_png, verify_chain

router = APIRouter()
export_router = APIRouter(prefix="/v1", dependencies=[Depends(require_write_token)])

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/evidence/verify")
def verify(session: SessionDep) -> dict:
    result = verify_chain(session)
    broken = result["first_broken"]
    result["message"] = "chain intact" if broken is None else f"record {broken['id']} broken: {broken['reason']}"
    return result


@router.get("/evidence/{evidence_id}/screenshot.png")
def screenshot(evidence_id: str, session: SessionDep, settings: SettingsDep) -> Response:
    evidence = session.get(Evidence, evidence_id)
    png = screenshot_png(evidence, captures_dir=settings.captures_dir) if evidence else None
    if png is None:
        raise HTTPException(404, "No screenshot for this record")
    return Response(png, media_type="image/png", headers={"X-Content-Type-Options": "nosniff"})


@export_router.get("/evidence/{evidence_id}.pdf")
def evidence_pdf(evidence_id: str, session: SessionDep, settings: SettingsDep) -> Response:
    try:
        pdf = render_pdf(session, evidence_id, captures_dir=settings.captures_dir)
    except LookupError:
        raise HTTPException(404, "Unknown evidence id") from None
    return Response(
        pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{evidence_id}.pdf"'}
    )


@export_router.get("/evidence/{evidence_id}.json")
def evidence_json(evidence_id: str, session: SessionDep) -> dict:
    try:
        return export_json(session, evidence_id)
    except LookupError:
        raise HTTPException(404, "Unknown evidence id") from None
