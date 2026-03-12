"""
AutoSlice — Ingestion handler.
Saves an uploaded file to disk and creates / restores a Job context.
"""

import uuid
from dataclasses import dataclass
from pathlib import Path

import aiofiles
from fastapi import UploadFile

from app.config import settings


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

    filename = file.filename or "upload.3mf"
    archive_path = job_dir / filename
    size = 0

    async with aiofiles.open(archive_path, "wb") as out:
        while chunk := await file.read(1024 * 64):
            await out.write(chunk)
            size += len(chunk)

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
    job_dir = settings.upload_dir / job_id
    if not job_dir.exists():
        return None

    archives = list(job_dir.glob("*.3mf"))
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
