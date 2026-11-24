from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Evidence
from app.schemas import EvidenceResponse

router = APIRouter()
export_router = APIRouter(prefix="/v1")

SessionDep = Annotated[Session, Depends(get_session)]


@export_router.get("/evidence/{evidence_id}.pdf", status_code=501)
def evidence_pdf(evidence_id: str) -> None:
    raise HTTPException(501, "PDF export is not implemented yet")


@export_router.get("/evidence/{evidence_id}.json", response_model=EvidenceResponse)
def evidence_json(evidence_id: str, session: SessionDep) -> Evidence:
    evidence = session.get(Evidence, evidence_id)
    if evidence is None:
        raise HTTPException(404, "Unknown evidence id")
    return evidence
