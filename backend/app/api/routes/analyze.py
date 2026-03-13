"""
AutoSlice — Analyze route.
GET /api/analyze/{job_id}
  Runs the full analysis pipeline and returns a JSON report.
"""

import asyncio
import dataclasses
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ingestion.handler import find_job
from app.ingestion.unpacker import unpack
from app.parser.model_parser import parse_model_files
from app.parser.metadata_extractor import extract_archive_metadata
from app.geometry.analyzer import analyze as run_geometry
from app.normalization.intent import normalize

router = APIRouter()


# ---------- Response schemas ----------

class BoundingBoxSchema(BaseModel):
    x_mm: float
    y_mm: float
    z_mm: float
    volume_cm3: float


class OverhangSchema(BaseModel):
    has_overhangs: bool
    max_angle_deg: float
    overhang_area_ratio: float


class BridgeSchema(BaseModel):
    has_bridges: bool
    max_span_mm: float


class ThinWallSchema(BaseModel):
    has_thin_walls: bool
    min_thickness_mm: float


class GeometrySchema(BaseModel):
    bounding_box: BoundingBoxSchema
    part_count: int
    mesh_is_watertight: bool
    estimated_volume_cm3: float
    surface_area_mm2: float
    contact_area_mm2: float
    height_to_base_ratio: float
    overhang: OverhangSchema
    bridge: BridgeSchema
    thin_wall: ThinWallSchema


class IntentSchema(BaseModel):
    difficulty: str
    needs_supports: bool
    support_density_hint: str
    needs_brim: bool
    size_class: str
    has_fine_detail: bool
    is_structurally_risky: bool
    support_risk: int
    adhesion_risk: int
    stability_risk: int
    detail_risk: int


class ModelInfoSchema(BaseModel):
    part_count: int
    unit: str


class ArchiveInfoSchema(BaseModel):
    filename: str
    size_bytes: int
    has_model_file: bool
    has_thumbnail: bool
    file_listing: list[str]


class AnalyzeResponse(BaseModel):
    job_id: str
    archive: ArchiveInfoSchema
    model: ModelInfoSchema
    geometry: GeometrySchema
    intent: IntentSchema


# ---------- Route ----------

@router.get("/analyze/{job_id}", response_model=AnalyzeResponse)
async def analyze(job_id: str) -> AnalyzeResponse:
    """
    Full analysis pipeline for a previously uploaded 3MF file.

    Pipeline:
      1. Look up job by job_id
      2. Unpack archive (skips if already extracted)
      3. Parse 3D/3dmodel.model XML
      4. Run geometry analysis (bounding box, overhangs, bridges)
      5. Normalize to ModelIntent
      6. Return structured JSON
    """
    job = find_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    loop = asyncio.get_event_loop()

    # Unpack if not already done (idempotent — zipfile just overwrites)
    archive = await loop.run_in_executor(
        None, unpack, job.archive_path, job.extract_dir
    )

    if not archive.model_files:
        raise HTTPException(
            status_code=422,
            detail="No .model files found in archive. Is this a valid 3MF file?",
        )

    # Parse all model files (handles Bambu multi-file 3MF)
    try:
        parsed_model = await loop.run_in_executor(
            None, parse_model_files, archive.model_files, archive.object_type_map
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse 3MF model: {exc}")

    if not parsed_model.objects:
        file_names = [f.name for f in archive.model_files]
        raise HTTPException(
            status_code=422,
            detail=f"No mesh objects found. Scanned {len(archive.model_files)} file(s): {file_names}",
        )

    # Geometry analysis (CPU-bound → thread pool)
    try:
        geometry = await loop.run_in_executor(None, run_geometry, parsed_model)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Geometry analysis failed: {exc}")

    # Normalize
    intent = normalize(geometry)

    # Archive metadata
    meta = extract_archive_metadata(
        original_filename=job.original_filename,
        size_bytes=job.size_bytes,
        extract_dir=job.extract_dir,
        all_files=archive.all_files,
    )

    return AnalyzeResponse(
        job_id=job_id,
        archive=ArchiveInfoSchema(
            filename=meta.original_filename,
            size_bytes=meta.size_bytes,
            has_model_file=meta.has_model_file,
            has_thumbnail=meta.has_thumbnail,
            file_listing=meta.all_file_paths,
        ),
        model=ModelInfoSchema(
            part_count=len(parsed_model.objects),
            unit=parsed_model.unit,
        ),
        geometry=GeometrySchema(
            bounding_box=BoundingBoxSchema(**dataclasses.asdict(geometry.bounding_box)),
            part_count=geometry.part_count,
            mesh_is_watertight=geometry.mesh_is_watertight,
            estimated_volume_cm3=geometry.estimated_volume_cm3,
            surface_area_mm2=geometry.surface_area_mm2,
            contact_area_mm2=geometry.contact_area_mm2,
            height_to_base_ratio=geometry.height_to_base_ratio,
            overhang=OverhangSchema(**dataclasses.asdict(geometry.overhang)),
            bridge=BridgeSchema(**dataclasses.asdict(geometry.bridge)),
            thin_wall=ThinWallSchema(**dataclasses.asdict(geometry.thin_wall)),
        ),
        intent=IntentSchema(
            difficulty=intent.difficulty,
            needs_supports=intent.needs_supports,
            support_density_hint=intent.support_density_hint,
            needs_brim=intent.needs_brim,
            size_class=intent.size_class,
            has_fine_detail=intent.has_fine_detail,
            is_structurally_risky=intent.is_structurally_risky,
            support_risk=intent.support_risk,
            adhesion_risk=intent.adhesion_risk,
            stability_risk=intent.stability_risk,
            detail_risk=intent.detail_risk,
        ),
    )
