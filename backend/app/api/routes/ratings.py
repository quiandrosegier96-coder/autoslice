"""
AutoSlice — Star ratings route.
POST /api/ratings      — submit 1–5 star rating for a conversion job
GET  /api/ratings/average — get average rating + count (public)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.dependencies import get_optional_user
from app.database import submit_rating, get_average_rating

router = APIRouter()


class RatingRequest(BaseModel):
    job_id: str
    stars: int = Field(ge=1, le=5)


@router.post("/ratings", status_code=201)
def post_rating(
    req: RatingRequest,
    current_user: dict | None = Depends(get_optional_user),
) -> dict:
    user_id = int(current_user["sub"]) if current_user else None
    submit_rating(req.job_id, user_id, req.stars)
    return {"message": "Rating submitted. Thank you!"}


@router.get("/ratings/average")
def average_rating() -> dict:
    return get_average_rating()
