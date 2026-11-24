from fastapi import APIRouter, Depends, HTTPException

from app import review as decisions
from app.auth import require_write_token
from app.deps import SessionDep
from app.schemas import ReviewRequest, ReviewResponse

router = APIRouter()


@router.post(
    "/review/{evidence_id}",
    response_model=ReviewResponse,
    dependencies=[Depends(require_write_token)],
    description="Officer decision. Confirm blocks the site; reject needs a reason and clears the site only for "
    "`legitimate_site` or `not_a_scam`. The note stays in the console.",
)
def review(evidence_id: str, body: ReviewRequest, session: SessionDep) -> ReviewResponse:
    try:
        outcome = decisions.review(session, evidence_id, body.decision, body.reviewer, body.reason, body.note)
    except LookupError:
        raise HTTPException(404, "Unknown evidence id") from None
    except decisions.ReviewRefused as refused:  # refused before anything was written
        status = 422 if body.decision == "reject" else 409
        raise HTTPException(status, str(refused)) from None
    session.commit()
    version = decisions.after_commit(outcome)
    return ReviewResponse(
        evidence_id=evidence_id, decision=outcome.review.decision, reviewer=outcome.review.reviewer,
        reviewed_at=outcome.review.reviewed_at, domain=outcome.domain, status=outcome.status,
        reason=outcome.review.reason, blocklist_version=version,
    )
