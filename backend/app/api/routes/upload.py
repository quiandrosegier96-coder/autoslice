"""
AutoSlice — Upload route.
POST /api/upload
  Receives a .3mf file, validates it, saves and unpacks it, returns a job_id.
"""

import asyncio

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.ingestion.handler import create_job, find_owned_job, remove_job
from app.ingestion.validator import validate_3mf_upload
from app.auth.dependencies import get_current_user
from app.database import log_job
from app.threemf.container.opc import primary_model_path, validate_relationships
from app.threemf.container.reader import ThreeMFContainer
from app.threemf.container.security import UnsafeThreeMFError

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
    current_user: dict = Depends(get_current_user),
) -> UploadResponse:
    """
    Accept a 3MF upload and validate it through the secure container.
    Legacy extraction is deferred to legacy analyze/convert callers.
    Returns job_id for use in /analyze and /convert calls.
    """
    await validate_3mf_upload(file)
    job = await create_job(file)

    # Read and validate through the bounded, non-extracting package container.
    loop = asyncio.get_event_loop()
    try:
        container = await loop.run_in_executor(None, ThreeMFContainer.from_path, job.archive_path)
        validate_relationships(container)
        model_path = primary_model_path(container)
    except (UnsafeThreeMFError, ValueError) as exc:
        remove_job(job.job_id)
        raise HTTPException(status_code=400, detail=f"Invalid or unsafe 3MF package: {exc}") from exc

    user_id = int(current_user["sub"])
    log_job(job.job_id, user_id, "upload", filename=job.original_filename)

    return UploadResponse(
        job_id=job.job_id,
        filename=job.original_filename,
        size_bytes=job.size_bytes,
        has_model_file=container.exists(model_path),
        has_thumbnail=any(path.lower().endswith((".png", ".jpg", ".jpeg")) for path in container.paths),
        archive_file_count=len(container.paths),
        message="File securely validated. Call /api/analyze/{job_id} to analyse.",
    )


@router.get("/upload/{job_id}/file")
async def get_upload_file(job_id: str, current_user: dict = Depends(get_current_user)):
    """Serve the original .3mf archive so the frontend viewer can load it."""
    job = find_owned_job(job_id, int(current_user["sub"]))
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return FileResponse(
        path=str(job.archive_path),
        media_type="model/3mf",
        filename=job.original_filename,
    )
