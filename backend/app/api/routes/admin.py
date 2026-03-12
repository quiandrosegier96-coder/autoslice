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
        users = conn.execute(
            "SELECT id, username, email, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
        result = []
        for u in users:
            uploads = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE user_id = ? AND action = 'upload'",
                (u["id"],)
            ).fetchone()[0]
            conversions = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE user_id = ? AND action = 'convert'",
                (u["id"],)
            ).fetchone()[0]
            result.append(UserRow(
                id=u["id"],
                username=u["username"],
                email=u["email"],
                created_at=u["created_at"],
                is_admin=u["email"] in ADMIN_EMAILS,
                uploads=uploads,
                conversions=conversions,
            ))
    return result


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
