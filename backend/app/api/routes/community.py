"""
AutoSlice — Community print sharing endpoints.
"""

import uuid
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.auth.dependencies import get_current_user, get_optional_user
from app.config import settings
from app.database import get_connection

router = APIRouter()

_ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_PHOTO_BYTES = 10 * 1024 * 1024   # 10 MB
_MAX_FILE_BYTES  = 100 * 1024 * 1024  # 100 MB


def _files_dir() -> Path:
    d = settings.upload_dir / "community" / "files"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _photos_dir() -> Path:
    d = settings.upload_dir / "community" / "photos"
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/community/upload")
async def community_upload(
    title: str = Form(...),
    description: str = Form(""),
    filament_type: str = Form(""),
    printer_name: str = Form(""),
    file: UploadFile = File(...),
    photo: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not (file.filename or "").lower().endswith(".3mf"):
        raise HTTPException(status_code=400, detail="Only .3mf files are allowed.")
    if photo.content_type not in _ALLOWED_PHOTO_TYPES:
        raise HTTPException(status_code=400, detail="Photo must be a JPEG, PNG, or WebP image.")
    if not title.strip():
        raise HTTPException(status_code=400, detail="Title is required.")

    photo_data = await photo.read()
    if len(photo_data) > _MAX_PHOTO_BYTES:
        raise HTTPException(status_code=400, detail="Photo must be under 10 MB.")

    file_data = await file.read()
    if len(file_data) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File must be under 100 MB.")

    file_id = uuid.uuid4().hex
    ext = Path(photo.filename or "photo.jpg").suffix.lower() or ".jpg"
    file_path  = _files_dir()  / f"{file_id}.3mf"
    photo_path = _photos_dir() / f"{file_id}{ext}"
    file_path.write_bytes(file_data)
    photo_path.write_bytes(photo_data)

    user_id = int(current_user["sub"])
    created_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
        username = row["username"] if row else "unknown"
        conn.execute(
            """INSERT INTO community_prints
               (user_id, username, title, description, filament_type, printer_name,
                filename, photo_filename, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (user_id, username, title.strip(), description.strip(),
             filament_type.strip(), printer_name.strip(),
             f"{file_id}.3mf", f"{file_id}{ext}", created_at),
        )
        conn.commit()
        new_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

    return {"id": new_id, "message": "Shared successfully."}


@router.get("/community")
def community_list(current_user: dict | None = Depends(get_optional_user)) -> list:
    user_id = int(current_user["sub"]) if current_user else None
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT cp.id, cp.user_id, cp.username, cp.title, cp.description,
                      cp.filament_type, cp.printer_name, cp.photo_filename,
                      cp.download_count, cp.created_at,
                      ROUND(AVG(cr.stars), 1) as avg_rating,
                      COUNT(cr.id) as rating_count
               FROM community_prints cp
               LEFT JOIN community_ratings cr ON cr.print_id = cp.id
               GROUP BY cp.id
               ORDER BY cp.created_at DESC"""
        ).fetchall()
        result = []
        for r in rows:
            item = dict(r)
            if user_id:
                own = conn.execute(
                    "SELECT stars FROM community_ratings WHERE print_id = ? AND user_id = ?",
                    (r["id"], user_id),
                ).fetchone()
                item["user_rating"] = own["stars"] if own else None
            else:
                item["user_rating"] = None
            result.append(item)
    return result


@router.get("/community/{print_id}/photo")
def community_photo(print_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT photo_filename FROM community_prints WHERE id = ?", (print_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Not found.")
    photo_path = _photos_dir() / row["photo_filename"]
    if not photo_path.exists():
        raise HTTPException(status_code=404, detail="Photo file not found.")
    return FileResponse(str(photo_path))


@router.get("/community/{print_id}/download")
def community_download(print_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT filename, title FROM community_prints WHERE id = ?", (print_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found.")
        conn.execute(
            "UPDATE community_prints SET download_count = download_count + 1 WHERE id = ?",
            (print_id,),
        )
        conn.commit()
    file_path = _files_dir() / row["filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    safe = "".join(c for c in row["title"] if c.isalnum() or c in " -_").strip() or "print"
    return FileResponse(str(file_path), filename=f"{safe}.3mf", media_type="application/zip")


class RateRequest(BaseModel):
    stars: int


@router.post("/community/{print_id}/rate")
def community_rate(
    print_id: int,
    req: RateRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not 1 <= req.stars <= 5:
        raise HTTPException(status_code=400, detail="Stars must be between 1 and 5.")
    user_id = int(current_user["sub"])
    created_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM community_prints WHERE id = ?", (print_id,)
        ).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Print not found.")
        conn.execute(
            """INSERT INTO community_ratings (print_id, user_id, stars, created_at)
               VALUES (?,?,?,?)
               ON CONFLICT(print_id, user_id)
               DO UPDATE SET stars = excluded.stars, created_at = excluded.created_at""",
            (print_id, user_id, req.stars, created_at),
        )
        conn.commit()
        row = conn.execute(
            "SELECT ROUND(AVG(stars), 1) as avg, COUNT(*) as cnt FROM community_ratings WHERE print_id = ?",
            (print_id,),
        ).fetchone()
    return {"avg_rating": row["avg"], "rating_count": row["cnt"]}
