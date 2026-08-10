"""Feature-flagged Universal3MF conversion and validation-gated download API."""

import asyncio
from dataclasses import dataclass
from functools import partial
import logging
from pathlib import Path
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.config import settings
from app.database import log_job
from app.ingestion.handler import find_job
from app.threemf.conversion import ConversionError, convert_3mf
from app.threemf.conversion.schemas import ConversionReportSchema, SourceSchema, TargetSchema
from app.threemf.domain.settings import ConversionContext, ConversionMode
from app.threemf.validation import validate_3mf

logger = logging.getLogger(__name__)
router = APIRouter()


class UniversalConvertRequest(BaseModel):
    job_id: str
    target_slicer: str = "anycubic"
    target_printer: str
    nozzle_size_mm: float = 0.4
    material: str = "pla"
    mode: ConversionMode = ConversionMode.AUTOSLICE
    source_slicer: str | None = None


class UniversalConvertResponse(BaseModel):
    success: bool
    source: SourceSchema
    target: TargetSchema
    compatibility: ConversionReportSchema
    output_filename: str
    download_reference: str
    validation_passed: bool
    fallback_used: bool = False


@dataclass(frozen=True)
class _DownloadRecord:
    user_id: int
    path: Path
    filename: str


_records: dict[str, _DownloadRecord] = {}
_records_lock = Lock()


@router.post("/universal-convert", response_model=UniversalConvertResponse)
async def universal_convert(
    request: UniversalConvertRequest,
    current_user: dict = Depends(get_current_user),
):
    if not settings.use_universal_3mf_engine:
        raise HTTPException(status_code=503, detail={
            "code": "UNIVERSAL_ENGINE_DISABLED",
            "message": "Universal3MF conversion is disabled. The explicit legacy endpoint remains available.",
        })
    job = find_job(request.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "JOB_NOT_FOUND", "message": "Upload job not found."})
    context = ConversionContext(
        target_slicer=request.target_slicer,
        target_printer_id=request.target_printer,
        nozzle_size_mm=request.nozzle_size_mm,
        material_id=request.material,
        mode=request.mode,
        source_slicer=request.source_slicer,
    )
    existing = {path.name for path in job.archive_path.parent.glob("*.3mf")}
    operation = partial(
        convert_3mf, job.archive_path, context,
        original_filename=job.original_filename, existing_filenames=existing,
        min_detection_confidence=settings.universal_3mf_min_confidence,
    )
    try:
        result = await asyncio.get_event_loop().run_in_executor(None, operation)
    except ConversionError as exc:
        logger.error(
            "Universal3MF conversion failed",
            extra={"job_id": request.job_id, "stage": exc.code.value, "reason": str(exc),
                   "legacy_fallback_available": settings.universal_3mf_legacy_fallback},
        )
        return JSONResponse(status_code=422, content={
            "success": False,
            "error": {"code": exc.code.value, "message": str(exc)},
            "legacy_fallback_available": settings.universal_3mf_legacy_fallback,
            "legacy_fallback_used": False,
        })
    output_path = job.archive_path.parent / result.output_filename
    try:
        with output_path.open("xb") as output_file:
            output_file.write(result.output)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail={
            "code": "OUTPUT_COLLISION", "message": "The generated output filename already exists; retry the conversion.",
        }) from exc
    report = ConversionReportSchema.from_result(result)
    user_id = int(current_user["sub"])
    with _records_lock:
        _records[result.conversion_id] = _DownloadRecord(user_id, output_path, result.output_filename)
    log_job(request.job_id, user_id, "universal_convert", filename=result.output_filename, printer_id=request.target_printer)
    return UniversalConvertResponse(
        success=True,
        source=report.source,
        target=report.target,
        compatibility=report,
        output_filename=result.output_filename,
        download_reference=f"/api/universal-convert/{result.conversion_id}/download",
        validation_passed=True,
        fallback_used=False,
    )


@router.get("/universal-convert/{conversion_id}/download")
async def universal_download(conversion_id: str, current_user: dict = Depends(get_current_user)):
    with _records_lock:
        record = _records.get(conversion_id)
    if record is None or record.user_id != int(current_user["sub"]):
        raise HTTPException(status_code=404, detail="Conversion output not found.")
    if not record.path.is_file():
        raise HTTPException(status_code=404, detail="Conversion output is no longer available.")
    validation = await asyncio.get_event_loop().run_in_executor(None, validate_3mf, record.path.read_bytes())
    if not validation.valid:
        raise HTTPException(status_code=409, detail="Conversion output failed its download validation gate.")
    return FileResponse(record.path, media_type="model/3mf", filename=record.filename)
