"""
AutoSlice — Ingestion handler.
Saves an uploaded file to disk and creates / restores a Job context.
"""

import uuid
from dataclasses import dataclass
from pathlib import Path
from shutil import rmtree

import aiofiles
from fastapi import HTTPException, UploadFile

from app.config import settings
from app.database import job_belongs_to_user


@dataclass
class Job:
    job_id: str
    original_filename: str
    size_bytes: int
    archive_path: Path      # path to the saved .3mf ZIP
    extract_dir: Path       # path to the extracted contents


async def create_job(file: UploadFile) -> Job:
    """
    Save the uploaded file to disk under a unique job directory.
    Returns a Job object with paths for downstream layers.
    """
    job_id = str(uuid.uuid4())
    job_dir = settings.upload_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    filename = Path((file.filename or "upload.3mf").replace("\\", "/")).name[:255]
    if not filename.lower().endswith(".3mf"):
        filename = "upload.3mf"
    # Never use a client-controlled name as a filesystem path.
    archive_path = job_dir / "source.3mf"
    size = 0

    try:
        async with aiofiles.open(archive_path, "xb") as out:
            while chunk := await file.read(1024 * 64):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum allowed size of {settings.max_upload_size_mb} MB.",
                    )
                await out.write(chunk)
    except Exception:
        rmtree(job_dir, ignore_errors=True)
        raise

    extract_dir = job_dir / "extracted"
    extract_dir.mkdir(exist_ok=True)

    return Job(
        job_id=job_id,
        original_filename=filename,
        size_bytes=size,
        archive_path=archive_path,
        extract_dir=extract_dir,
    )


def find_job(job_id: str) -> Job | None:
    """
    Reconstruct a Job from an existing job directory on disk.
    Returns None if the job_id is unknown or the archive is missing.
    """
    try:
        canonical_job_id = str(uuid.UUID(job_id))
    except (ValueError, AttributeError, TypeError):
        return None
    job_dir = settings.upload_dir / canonical_job_id
    if not job_dir.exists():
        return None

    archives = sorted(job_dir.glob("*.3mf"))
    if not archives:
        return None

    archive_path = archives[0]
    extract_dir = job_dir / "extracted"
    extract_dir.mkdir(exist_ok=True)

    return Job(
        job_id=job_id,
        original_filename=archive_path.name,
        size_bytes=archive_path.stat().st_size,
        archive_path=archive_path,
        extract_dir=extract_dir,
    )


def find_owned_job(job_id: str, user_id: int) -> Job | None:
    """Resolve a job only when it belongs to the authenticated user."""
    if not job_belongs_to_user(job_id, user_id):
        return None
    return find_job(job_id)


def remove_job(job_id: str) -> None:
    """Remove one UUID-isolated job workspace; ignore invalid identifiers."""
    try:
        canonical_job_id = str(uuid.UUID(job_id))
    except (ValueError, AttributeError, TypeError):
        return
    target = (settings.upload_dir / canonical_job_id).resolve()
    if target.parent == settings.upload_dir.resolve():
        rmtree(target, ignore_errors=True)
