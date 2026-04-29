"""
AutoSlice — Review Pydantic schemas.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ReviewCreate(BaseModel):
    name: str = Field(..., max_length=80)
    rating: int = Field(..., ge=1, le=5)
    text: str = Field(..., max_length=1000)
    app_version: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = str(v).strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, v: str) -> str:
        v = str(v).strip()
        if not v:
            raise ValueError("text cannot be empty")
        return v


class CreateReviewResponse(BaseModel):
    ok: bool
    message: str


class ReviewPublic(BaseModel):
    id: int
    name: str
    rating: int
    text: str
    app_version: str | None
    created_at: str


class ReviewAdmin(BaseModel):
    id: int
    name: str
    rating: int
    text: str
    app_version: str | None
    approved: bool
    created_at: str
    approved_at: str | None


class PublicReviewsResponse(BaseModel):
    average_rating: float
    total_reviews: int
    reviews: list[ReviewPublic]
