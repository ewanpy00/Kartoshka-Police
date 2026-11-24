from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.deps import SessionDep
from app.evidence import pdf
from app.models import Evidence
from app.schemas import EvidenceResponse

router = APIRouter()


def load(session, evidence_id: str) -> Evidence:
    evidence = session.get(Evidence, evidence_id)
    if evidence is None:
        raise HTTPException(404, "Unknown evidence id")
    return evidence


@router.get("/evidence/{evidence_id}.json", response_model=EvidenceResponse)
def evidence_json(evidence_id: str, session: SessionDep) -> Evidence:
    return load(session, evidence_id)


@router.get("/evidence/{evidence_id}.pdf", response_class=Response,
            description="The evidence record as a PDF (Arabic and English), with artifact hashes and the chain hash.")
def evidence_pdf(evidence_id: str, session: SessionDep) -> Response:
    evidence = load(session, evidence_id)
    return Response(pdf.render(session, evidence), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{evidence_id}.pdf"'})
