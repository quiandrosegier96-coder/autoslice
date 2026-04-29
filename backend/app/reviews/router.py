"""
AutoSlice — Reviews API router.

Public:
  POST /api/reviews               Submit a review (pending approval)
  GET  /api/reviews/public        Fetch approved reviews + aggregate stats

Admin (requires valid admin JWT):
  GET    /api/admin/reviews                       List all reviews
  PATCH  /api/admin/reviews/{review_id}/approve   Approve a review
  DELETE /api/admin/reviews/{review_id}           Delete a review
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_admin_user
from app.reviews import service
from app.reviews.schemas import (
    CreateReviewResponse,
    PublicReviewsResponse,
    ReviewAdmin,
    ReviewCreate,
)

router = APIRouter()


@router.post(
    "/reviews",
    response_model=CreateReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a review",
    response_description="Confirmation that the review was received and is pending approval",
)
def submit_review(body: ReviewCreate) -> CreateReviewResponse:
    service.create_review(body)
    return CreateReviewResponse(
        ok=True,
        message="Review ontvangen en wacht op goedkeuring.",
    )


@router.get(
    "/reviews/public",
    response_model=PublicReviewsResponse,
    summary="Get approved public reviews with aggregate stats",
)
def public_reviews() -> PublicReviewsResponse:
    return service.get_public_reviews()


@router.get(
    "/admin/reviews",
    response_model=list[ReviewAdmin],
    summary="Admin: list all reviews including unapproved",
)
def admin_list_reviews(_: dict = Depends(get_admin_user)) -> list[ReviewAdmin]:
    return service.list_all_reviews()


@router.patch(
    "/admin/reviews/{review_id}/approve",
    response_model=dict,
    summary="Admin: approve a pending review",
)
def admin_approve_review(
    review_id: int,
    _: dict = Depends(get_admin_user),
) -> dict:
    if not service.approve_review(review_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found.")
    return {"ok": True}


@router.delete(
    "/admin/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Admin: permanently delete a review",
)
def admin_delete_review(
    review_id: int,
    _: dict = Depends(get_admin_user),
) -> None:
    if not service.delete_review(review_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found.")
