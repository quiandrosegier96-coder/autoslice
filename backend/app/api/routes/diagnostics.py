"""
AutoSlice — Diagnostics routes (admin only).

GET /api/admin/decision-trace/{job_id}
    Returns the decision trace + settings delta for a completed conversion.
    Shows exactly which rules fired, why, and what changed from base profile.
"""

from fastapi import APIRouter, HTTPException

from app.auth.dependencies import get_admin_user as require_admin
from app.database import get_generation_trace
from fastapi import Depends

router = APIRouter()


@router.get("/admin/decision-trace/{job_id}")
def get_decision_trace(
    job_id: str,
    _: dict = Depends(require_admin),
) -> dict:
    """
    Full decision audit for a conversion job.

    Returns:
      - decision_trace: list of {rule, trigger, field, before, after}
        showing every rule that fired and changed a setting
      - settings_delta: dict of {field: {from, to}} — diff vs base profile
      - risk scores and metadata
    """
    result = get_generation_trace(job_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No traced conversion found for job '{job_id}'. "
                   "Only conversions made after the diagnostic upgrade are traced.",
        )
    return result
