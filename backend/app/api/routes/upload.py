"""
AutoSlice — Upload route.
POST /api/upload
  Receives a .3mf file, validates it, saves and unpacks it, returns a job_id.
"""

import asyncio

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.ingestion.handler import create_job, find_job
from app.ingestion.validator import validate_3mf_upload
from app.ingestion.unpacker import unpack
from app.auth.dependencies import get_optional_user
from app.database import log_job

router = APIRouter()


class UploadResponse(BaseModel):
    job_id: str
    filename: str
    size_bytes: int
    has_model_file: bool
    has_thumbnail: bool
    archive_file_count: int
    message: str


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict | None = Depends(get_optional_user),
) -> UploadResponse:
    """
    Accept a Bambu/MakerWorld .3mf file upload.
    Validates, saves, and immediately unpacks the archive.
    Returns job_id for use in /analyze and /convert calls.
    """
    await validate_3mf_upload(file)
    job = await create_job(file)

    # Unpack in a thread so we don't block the event loop
    loop = asyncio.get_event_loop()
    archive = await loop.run_in_executor(
        None, unpack, job.archive_path, job.extract_dir
    )

    user_id = int(current_user["sub"]) if current_user else None
    log_job(job.job_id, user_id, "upload", filename=job.original_filename)

    return UploadResponse(
        job_id=job.job_id,
        filename=job.original_filename,
        size_bytes=job.size_bytes,
        has_model_file=archive.model_file is not None,
        has_thumbnail=len(archive.thumbnail_files) > 0,
        archive_file_count=len(archive.all_files),
        message="File uploaded and unpacked. Call /api/analyze/{job_id} to analyse.",
    )


@router.get("/upload/{job_id}/file")
async def get_upload_file(job_id: str):
    """Serve the original .3mf archive so the frontend viewer can load it."""
    job = find_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return FileResponse(
        path=str(job.archive_path),
        media_type="model/3mf",
        filename=job.original_filename,
        headers={"Access-Control-Allow-Origin": "*"},
    )
