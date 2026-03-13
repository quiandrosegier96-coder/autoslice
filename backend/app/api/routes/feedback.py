"""
AutoSlice — Print feedback route.
POST /api/feedback — record how a printed job turned out.
No auth required: identified by job_id only.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.auth.dependencies import get_optional_user
from app.database import log_feedback
from fastapi import Depends

router = APIRouter()

_VALID_OUTCOMES = {
    "printed_ok",
    "supports_unneeded",
    "supports_missing",
    "stringing",
    "weak_part",
    "poor_surface",
    "detached_from_bed",
    "collapsed",
    "details_lost",
}


class FeedbackRequest(BaseModel):
    job_id: str
    outcome: str
    notes: str | None = None


@router.post("/feedback", status_code=201)
def submit_feedback(
    req: FeedbackRequest,
    current_user: dict | None = Depends(get_optional_user),
) -> dict:
    if req.outcome not in _VALID_OUTCOMES:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid outcome. Valid: {sorted(_VALID_OUTCOMES)}")

    user_id = int(current_user["sub"]) if current_user else None
    log_feedback(req.job_id, user_id, req.outcome, req.notes)
    return {"message": "Feedback recorded. Thank you!"}
