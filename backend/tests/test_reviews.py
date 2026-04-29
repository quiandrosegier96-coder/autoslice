"""
Tests for the reviews module.

Coverage:
  A — Schema validation      : rating range, empty fields rejected
  B — Service: create        : review stored as unapproved
  C — Service: public view   : unapproved hidden, approved visible
  D — Service: seed fallback : 4.3 / 128 when no approved reviews
  E — Service: real average  : calculated from approved ratings only
  F — Service: admin ops     : approve and delete
  G — HTTP: public endpoint  : response shape, filtering
  H — HTTP: admin endpoints  : approve, delete, list
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.reviews.schemas import ReviewCreate


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def db(tmp_path, monkeypatch):
    """Isolated SQLite DB per test — monkeypatches DB_PATH before any DB call."""
    db_file = tmp_path / "test_reviews.db"
    monkeypatch.setattr("app.database.DB_PATH", db_file)
    from app.database import init_db
    init_db()
    yield db_file


@pytest.fixture()
def client(db, monkeypatch):
    """
    TestClient with:
      - DB pointing at temp file (from `db` fixture)
      - seed_admin_users patched out (avoids slow PBKDF2 hashes on each startup)
      - get_admin_user overridden to always pass as admin
    """
    import app.main as _main
    monkeypatch.setattr(_main, "seed_admin_users", lambda: None)

    from app.auth.dependencies import get_admin_user
    _main.app.dependency_overrides[get_admin_user] = lambda: {
        "sub": "1", "email": "admin@test.com", "is_admin": True
    }

    with TestClient(_main.app) as c:
        yield c

    _main.app.dependency_overrides.clear()


def _make_review(**overrides) -> ReviewCreate:
    defaults = dict(name="Jeroen V.", rating=5, text="Super handige tool!", app_version="1.5.33")
    return ReviewCreate(**{**defaults, **overrides})


# ─────────────────────────────────────────────────────────────────────────────
# A — Schema validation
# ─────────────────────────────────────────────────────────────────────────────

def test_invalid_rating_too_high():
    with pytest.raises(ValidationError):
        ReviewCreate(name="Test", rating=6, text="Good")


def test_invalid_rating_too_low():
    with pytest.raises(ValidationError):
        ReviewCreate(name="Test", rating=0, text="Good")


def test_empty_text_rejected():
    with pytest.raises(ValidationError):
        ReviewCreate(name="Test", rating=4, text="   ")


def test_empty_name_rejected():
    with pytest.raises(ValidationError):
        ReviewCreate(name="  ", rating=4, text="Good review")


def test_name_trimmed():
    r = ReviewCreate(name="  Alice  ", rating=3, text="Nice")
    assert r.name == "Alice"


def test_text_trimmed():
    r = ReviewCreate(name="Alice", rating=3, text="  Nice app  ")
    assert r.text == "Nice app"


def test_name_max_length_rejected():
    with pytest.raises(ValidationError):
        ReviewCreate(name="x" * 81, rating=3, text="Good")


def test_text_max_length_rejected():
    with pytest.raises(ValidationError):
        ReviewCreate(name="Alice", rating=3, text="x" * 1001)


# ─────────────────────────────────────────────────────────────────────────────
# B — Service: create stores review as unapproved
# ─────────────────────────────────────────────────────────────────────────────

def test_create_review_stored_unapproved(db):
    from app.reviews.service import create_review, list_all_reviews
    create_review(_make_review())
    reviews = list_all_reviews()
    assert len(reviews) == 1
    assert reviews[0].approved is False
    assert reviews[0].name == "Jeroen V."
    assert reviews[0].rating == 5


# ─────────────────────────────────────────────────────────────────────────────
# C — Service: public view hides unapproved, shows approved
# ─────────────────────────────────────────────────────────────────────────────

def test_unapproved_not_in_public(db):
    from app.reviews.service import create_review, get_public_reviews
    create_review(_make_review())
    result = get_public_reviews()
    assert result.reviews == []


def test_approved_review_appears_publicly(db):
    from app.reviews.service import approve_review, create_review, get_public_reviews, list_all_reviews
    create_review(_make_review(name="Sarah M.", rating=4, text="Werkt perfect!"))
    review_id = list_all_reviews()[0].id
    approve_review(review_id)
    result = get_public_reviews()
    assert len(result.reviews) == 1
    assert result.reviews[0].name == "Sarah M."


# ─────────────────────────────────────────────────────────────────────────────
# D — Service: seed fallback when no approved reviews
# ─────────────────────────────────────────────────────────────────────────────

def test_seed_fallback_no_reviews(db):
    from app.reviews.service import get_public_reviews
    result = get_public_reviews()
    assert result.average_rating == 4.3
    assert result.total_reviews == 128
    assert result.reviews == []


def test_seed_fallback_with_unapproved_only(db):
    from app.reviews.service import create_review, get_public_reviews
    create_review(_make_review(rating=1))
    create_review(_make_review(rating=2))
    result = get_public_reviews()
    assert result.average_rating == 4.3
    assert result.total_reviews == 128


# ─────────────────────────────────────────────────────────────────────────────
# E — Service: real average calculated from approved ratings only
# ─────────────────────────────────────────────────────────────────────────────

def test_average_rating_from_approved(db):
    from app.reviews.service import approve_review, create_review, get_public_reviews, list_all_reviews
    create_review(_make_review(rating=5))
    create_review(_make_review(rating=3))
    create_review(_make_review(rating=1))  # will stay unapproved
    # list_all_reviews() returns newest-first: [rating=1, rating=3, rating=5]
    rows = list_all_reviews()
    approve_review(rows[1].id)  # rating=3
    approve_review(rows[2].id)  # rating=5
    result = get_public_reviews()
    assert result.average_rating == 4.0   # (5+3)/2
    assert result.total_reviews == 128    # max(2, 128) = 128


def test_total_reviews_exceeds_seed_when_many_approved(db):
    from app.reviews.service import approve_review, create_review, get_public_reviews, list_all_reviews
    for i in range(130):
        create_review(_make_review(rating=5, text=f"Review number {i}"))
    for row in list_all_reviews():
        approve_review(row.id)
    result = get_public_reviews()
    assert result.total_reviews == 130


# ─────────────────────────────────────────────────────────────────────────────
# F — Service: admin operations
# ─────────────────────────────────────────────────────────────────────────────

def test_admin_approve_sets_approved_flag(db):
    from app.reviews.service import approve_review, create_review, list_all_reviews
    create_review(_make_review())
    review_id = list_all_reviews()[0].id
    result = approve_review(review_id)
    assert result is True
    updated = list_all_reviews()[0]
    assert updated.approved is True
    assert updated.approved_at is not None


def test_admin_approve_nonexistent_returns_false(db):
    from app.reviews.service import approve_review
    assert approve_review(9999) is False


def test_admin_delete_removes_review(db):
    from app.reviews.service import create_review, delete_review, list_all_reviews
    create_review(_make_review())
    review_id = list_all_reviews()[0].id
    result = delete_review(review_id)
    assert result is True
    assert list_all_reviews() == []


def test_admin_delete_nonexistent_returns_false(db):
    from app.reviews.service import delete_review
    assert delete_review(9999) is False


# ─────────────────────────────────────────────────────────────────────────────
# G — HTTP: public endpoint
# ─────────────────────────────────────────────────────────────────────────────

def test_http_submit_review_returns_pending_message(client):
    resp = client.post("/api/reviews", json={
        "name": "Jeroen V.",
        "rating": 5,
        "text": "Super handige tool!",
        "app_version": "1.5.33",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["ok"] is True
    assert "goedkeuring" in body["message"]


def test_http_public_endpoint_hides_unapproved(client):
    client.post("/api/reviews", json={"name": "Test", "rating": 3, "text": "Pending review"})
    resp = client.get("/api/reviews/public")
    assert resp.status_code == 200
    body = resp.json()
    assert body["reviews"] == []
    assert body["average_rating"] == 4.3
    assert body["total_reviews"] == 128


def test_http_public_endpoint_shows_approved(client):
    from app.reviews.service import approve_review, list_all_reviews
    client.post("/api/reviews", json={"name": "Lisa K.", "rating": 4, "text": "Top tool!"})
    review_id = list_all_reviews()[0].id
    approve_review(review_id)
    resp = client.get("/api/reviews/public")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["reviews"]) == 1
    assert body["reviews"][0]["name"] == "Lisa K."


def test_http_invalid_rating_rejected(client):
    resp = client.post("/api/reviews", json={"name": "Test", "rating": 6, "text": "Bad rating"})
    assert resp.status_code == 422


def test_http_empty_text_rejected(client):
    resp = client.post("/api/reviews", json={"name": "Test", "rating": 4, "text": "   "})
    assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# H — HTTP: admin endpoints
# ─────────────────────────────────────────────────────────────────────────────

def test_http_admin_list_includes_unapproved(client):
    client.post("/api/reviews", json={"name": "Max R.", "rating": 5, "text": "Geweldig!"})
    resp = client.get("/api/admin/reviews")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["approved"] is False


def test_http_admin_approve(client):
    client.post("/api/reviews", json={"name": "Emma D.", "rating": 4, "text": "Eenvoudig!"})
    review_id = client.get("/api/admin/reviews").json()[0]["id"]
    resp = client.patch(f"/api/admin/reviews/{review_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    # Verify it now appears publicly
    pub = client.get("/api/reviews/public").json()
    assert len(pub["reviews"]) == 1


def test_http_admin_delete(client):
    client.post("/api/reviews", json={"name": "Thomas B.", "rating": 5, "text": "Nauwkeurig!"})
    review_id = client.get("/api/admin/reviews").json()[0]["id"]
    resp = client.delete(f"/api/admin/reviews/{review_id}")
    assert resp.status_code == 204
    assert client.get("/api/admin/reviews").json() == []


def test_http_admin_approve_nonexistent_returns_404(client):
    resp = client.patch("/api/admin/reviews/9999/approve")
    assert resp.status_code == 404


def test_http_admin_delete_nonexistent_returns_404(client):
    resp = client.delete("/api/admin/reviews/9999")
    assert resp.status_code == 404
