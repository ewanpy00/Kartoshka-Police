from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.auth import require_write_token
from app.deps import SessionDep
from app.evidence import pdf, store
from app.models import Evidence
from app.schemas import EvidenceResponse

router = APIRouter()
write_only = [Depends(require_write_token)]


def load(session, evidence_id: str) -> Evidence:
    evidence = session.get(Evidence, evidence_id)
    if evidence is None:
        raise HTTPException(404, "Unknown evidence id")
    return evidence


@router.get("/evidence/{evidence_id}.json", response_model=EvidenceResponse, dependencies=write_only,
            description="The evidence record as JSON. Needs the write token.")
def evidence_json(evidence_id: str, session: SessionDep) -> Evidence:
    return load(session, evidence_id)


@router.get("/evidence/{evidence_id}.pdf", response_class=Response, dependencies=write_only,
            description="The evidence record as a PDF (Arabic and English), with artifact hashes and the chain hash. "
            "Needs the write token.")
def evidence_pdf(evidence_id: str, session: SessionDep) -> Response:
    evidence = load(session, evidence_id)
    return Response(pdf.render(session, evidence), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{evidence_id}.pdf"'})


@router.get("/admin/evidence/verify", dependencies=write_only,
            description="Recompute the hash chain. Names the first broken record and whether its payload hash or "
            "its link to the previous record failed.")
def evidence_verify(session: SessionDep) -> dict:
    result = store.verify(session)
    broken = result["first_broken"]
    result["message"] = "chain intact" if broken is None else (
        f"record {broken['id']} (seq {broken['seq']}) broken: {broken['reason']}")
    return result


@router.get("/admin/evidence/{evidence_id}/screenshot.png", response_class=Response, dependencies=write_only,
            description="The stored phone screenshot. Served only when the file is inside the captures directory "
            "and begins with the PNG signature.")
def evidence_screenshot(evidence_id: str, session: SessionDep) -> Response:
    load(session, evidence_id)
    png = store.screenshot_png(session, evidence_id)
    if png is None:
        raise HTTPException(404, "No screenshot for this record")
    return Response(png, media_type="image/png", headers={"X-Content-Type-Options": "nosniff"})
