"""
AutoSlice — Admin routes.
GET /api/admin/users  — list all users with upload/convert counts
GET /api/admin/stats  — overall platform stats
Only accessible by admin accounts (admin1@prints.be, admin2@prints.be).
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import get_admin_user
from app.database import get_connection

router = APIRouter()


class UserRow(BaseModel):
    id: int
    username: str
    email: str
    created_at: str
    is_admin: bool
    uploads: int
    conversions: int


class StatsResponse(BaseModel):
    total_users: int
    total_uploads: int
    total_conversions: int


class RecentJob(BaseModel):
    job_id: str
    username: str | None
    email: str | None
    action: str
    filename: str | None
    printer_id: str | None
    created_at: str


@router.get("/admin/users", response_model=list[UserRow])
def list_users(_: dict = Depends(get_admin_user)) -> list[UserRow]:
    from app.database import ADMIN_EMAILS
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT u.id, u.username, u.email, u.created_at,
                   COALESCE(SUM(CASE WHEN j.action = 'upload'  THEN 1 ELSE 0 END), 0) AS uploads,
                   COALESCE(SUM(CASE WHEN j.action = 'convert' THEN 1 ELSE 0 END), 0) AS conversions
            FROM users u
            LEFT JOIN jobs j ON j.user_id = u.id
            GROUP BY u.id
            ORDER BY u.created_at DESC
        """).fetchall()
    return [
        UserRow(
            id=r["id"], username=r["username"], email=r["email"],
            created_at=r["created_at"], is_admin=r["email"] in ADMIN_EMAILS,
            uploads=r["uploads"], conversions=r["conversions"],
        )
        for r in rows
    ]


@router.get("/admin/stats", response_model=StatsResponse)
def get_stats(_: dict = Depends(get_admin_user)) -> StatsResponse:
    with get_connection() as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_uploads = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE action = 'upload'"
        ).fetchone()[0]
        total_conversions = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE action = 'convert'"
        ).fetchone()[0]
    return StatsResponse(
        total_users=total_users,
        total_uploads=total_uploads,
        total_conversions=total_conversions,
    )


class ResetTokenRow(BaseModel):
    id: int
    email: str
    token: str
    created_at: str
    used: bool


@router.get("/admin/reset-tokens", response_model=list[ResetTokenRow])
def list_reset_tokens(_: dict = Depends(get_admin_user)) -> list[ResetTokenRow]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, email, token, created_at, used FROM reset_tokens ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
    return [ResetTokenRow(id=r["id"], email=r["email"], token=r["token"],
                          created_at=r["created_at"], used=bool(r["used"])) for r in rows]


@router.get("/admin/recent", response_model=list[RecentJob])
def get_recent(_: dict = Depends(get_admin_user)) -> list[RecentJob]:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT j.job_id, u.username, u.email, j.action, j.filename, j.printer_id, j.created_at
            FROM jobs j
            LEFT JOIN users u ON j.user_id = u.id
            ORDER BY j.created_at DESC
            LIMIT 50
        """).fetchall()
    return [RecentJob(**dict(r)) for r in rows]


class GenerationLogRow(BaseModel):
    id: int
    job_id: str
    printer_id: str | None
    filament_type: str | None
    nozzle_size_mm: float | None
    bbox_x: float | None
    bbox_y: float | None
    bbox_z: float | None
    volume_cm3: float | None
    contact_area_mm2: float | None
    height_to_base_ratio: float | None
    overhang_ratio: float | None
    bridge_span_mm: float | None
    thin_wall_mm: float | None
    support_risk: int | None
    adhesion_risk: int | None
    stability_risk: int | None
    detail_risk: int | None
    created_at: str


@router.get("/admin/engine-log", response_model=list[GenerationLogRow])
def get_engine_log(_: dict = Depends(get_admin_user)) -> list[GenerationLogRow]:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, job_id, printer_id, filament_type, nozzle_size_mm,
                   bbox_x, bbox_y, bbox_z, volume_cm3,
                   contact_area_mm2, height_to_base_ratio,
                   overhang_ratio, bridge_span_mm, thin_wall_mm,
                   support_risk, adhesion_risk, stability_risk, detail_risk,
                   created_at
            FROM generation_log ORDER BY created_at DESC LIMIT 100
        """).fetchall()
    return [GenerationLogRow(**dict(r)) for r in rows]


class FeedbackRow(BaseModel):
    id: int
    job_id: str
    username: str | None
    outcome: str
    notes: str | None
    created_at: str


@router.get("/admin/feedback", response_model=list[FeedbackRow])
def get_feedback(_: dict = Depends(get_admin_user)) -> list[FeedbackRow]:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT f.id, f.job_id, u.username, f.outcome, f.notes, f.created_at
            FROM print_feedback f
            LEFT JOIN users u ON f.user_id = u.id
            ORDER BY f.created_at DESC LIMIT 100
        """).fetchall()
    return [FeedbackRow(**dict(r)) for r in rows]
