"""
AutoSlice — Review service layer (raw SQLite, matches project style).
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.database import get_connection
from app.reviews.schemas import (
    CreateReviewResponse,
    PublicReviewsResponse,
    ReviewAdmin,
    ReviewCreate,
    ReviewPublic,
)

_SEED_AVERAGE: float = 4.3
_SEED_TOTAL:   int   = 128


def create_review(data: ReviewCreate) -> None:
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO reviews (name, rating, text, app_version, approved, created_at)
               VALUES (?, ?, ?, ?, 0, ?)""",
            (data.name, data.rating, data.text, data.app_version, created_at),
        )
        conn.commit()


def get_public_reviews() -> PublicReviewsResponse:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, rating, text, app_version, created_at "
            "FROM reviews WHERE approved = 1 ORDER BY created_at DESC"
        ).fetchall()
        agg = conn.execute(
            "SELECT ROUND(AVG(CAST(rating AS REAL)), 1) AS avg, COUNT(*) AS total "
            "FROM reviews WHERE approved = 1"
        ).fetchone()

    count  = agg["total"] or 0
    db_avg = agg["avg"]

    average_rating = round(float(db_avg), 1) if count > 0 else _SEED_AVERAGE
    total_reviews  = max(count, _SEED_TOTAL)

    reviews = [
        ReviewPublic(
            id          = row["id"],
            name        = row["name"],
            rating      = row["rating"],
            text        = row["text"],
            app_version = row["app_version"],
            created_at  = row["created_at"],
        )
        for row in rows
    ]

    return PublicReviewsResponse(
        average_rating = average_rating,
        total_reviews  = total_reviews,
        reviews        = reviews,
    )


def list_all_reviews() -> list[ReviewAdmin]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, rating, text, app_version, approved, created_at, approved_at "
            "FROM reviews ORDER BY created_at DESC"
        ).fetchall()
    return [
        ReviewAdmin(
            id          = row["id"],
            name        = row["name"],
            rating      = row["rating"],
            text        = row["text"],
            app_version = row["app_version"],
            approved    = bool(row["approved"]),
            created_at  = row["created_at"],
            approved_at = row["approved_at"],
        )
        for row in rows
    ]


def approve_review(review_id: int) -> bool:
    approved_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        result = conn.execute(
            "UPDATE reviews SET approved = 1, approved_at = ? WHERE id = ?",
            (approved_at, review_id),
        )
        conn.commit()
    return result.rowcount > 0


def delete_review(review_id: int) -> bool:
    with get_connection() as conn:
        result = conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        conn.commit()
    return result.rowcount > 0
