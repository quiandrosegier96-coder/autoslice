"""
AutoSlice — AI router.

POST /api/ai/auto-settings
  Accepts explicit model geometry features and print intent.
  Returns AI-generated slicer settings, a risk score, and actionable warnings.

GET  /api/ai/auto-settings/{job_id}
  Pipeline-integrated variant: looks up an uploaded job, runs the geometry
  analysis pipeline (same steps as /api/analyze), then feeds the result
  directly into the AI engine. No geometry numbers required from the caller.

POST /api/ai/orientation-suggestion
  Accepts bounding-box geometry features and current rotation.
  Returns the recommended 90° rotation with confidence, scores, and warnings.
  Advisory only — slicing is unchanged unless the user clicks Apply Orientation.
"""

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.ai import auto_settings, orientation
from app.ai.schemas import (
    AutoSettingsRequest,
    AutoSettingsResponse,
    FilamentType,
    ModelFeatures,
    OrientationRequest,
    OrientationSuggestion,
)
from app.ingestion.handler import find_job
from app.ingestion.unpacker import unpack
from app.parser.model_parser import parse_model_files
from app.geometry.analyzer import analyze_mesh
from app.geometry.mesh_loader import merge_meshes

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# POST — caller supplies geometry features explicitly
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/ai/auto-settings",
    response_model=AutoSettingsResponse,
    summary="Generate AI-recommended print settings from explicit features",
    response_description="Generated settings, risk score, and warnings for the given model.",
)
def auto_settings_from_features(request: AutoSettingsRequest) -> AutoSettingsResponse:
    """
    Analyse model geometry features and return AI-generated slicer settings.

    - **features**: geometry measurements extracted from the model file
    - **filament**: material type (pla / petg / abs / asa / tpu / nylon)
    - **nozzle_mm**: nozzle diameter in millimetres (default 0.4)
    - **quality_intent**: target quality level — `draft`, `standard`, or `quality`
    """
    try:
        return auto_settings.run(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Auto-settings engine error: {exc}") from exc


# ─────────────────────────────────────────────────────────────────────────────
# GET — pipeline-integrated: job_id + optional print intent as query params
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/ai/auto-settings/{job_id}",
    response_model=AutoSettingsResponse,
    summary="Generate AI-recommended print settings for an uploaded job",
    response_description="Generated settings, risk score, and warnings derived from the model geometry.",
)
async def auto_settings_for_job(
    job_id: str,
    filament: FilamentType = Query(default=FilamentType.PLA, description="Filament material type."),
    nozzle_mm: float = Query(default=0.4, gt=0, description="Nozzle diameter in mm."),
    quality_intent: Literal["draft", "standard", "quality"] = Query(
        default="standard",
        description="Target quality level.",
    ),
) -> AutoSettingsResponse:
    """
    Full pipeline integration: unpack → parse → geometry analysis → AI engine.

    Reuses the same geometry analysis steps as `GET /api/analyze/{job_id}`.
    The caller only needs to supply print intent (filament, nozzle, quality) —
    all geometry measurements are derived automatically from the uploaded file.
    """
    job = find_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    loop = asyncio.get_event_loop()

    archive = await loop.run_in_executor(None, unpack, job.archive_path, job.extract_dir)
    if not archive.model_files:
        raise HTTPException(status_code=422, detail="No model files found in archive.")

    try:
        parsed_model = await loop.run_in_executor(
            None, parse_model_files, archive.model_files, archive.object_type_map
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Parse failed: {exc}")

    if not parsed_model.objects:
        raise HTTPException(status_code=422, detail="No mesh objects found.")

    try:
        mesh = await loop.run_in_executor(None, merge_meshes, parsed_model.objects)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to load mesh: {exc}")

    try:
        geometry = await loop.run_in_executor(
            None, analyze_mesh, mesh, len(parsed_model.objects)
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Geometry analysis failed: {exc}")

    features = auto_settings.features_from_geometry(geometry, nozzle_mm)

    request = AutoSettingsRequest(
        features       = features,
        filament       = filament,
        nozzle_mm      = nozzle_mm,
        quality_intent = quality_intent,
    )

    try:
        return auto_settings.run(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Auto-settings engine error: {exc}") from exc


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/ai/orientation-suggestion
# Advisory only — never modifies slicing behaviour unless the user applies it.
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/ai/orientation-suggestion",
    response_model=OrientationSuggestion,
    summary="Suggest the best 90° model rotation before slicing",
    response_description=(
        "Recommended rotation, confidence, support-reduction estimate, "
        "scores, warnings, and orientation_hints for the Apply Orientation flow."
    ),
)
def orientation_suggestion(request: OrientationRequest) -> OrientationSuggestion:
    """
    Analyse bounding-box geometry features and suggest the optimal 90° rotation.

    Returns an advisory suggestion only. Slicing behaviour is unchanged unless
    the user explicitly clicks **Apply Orientation**, which merges
    `orientation_hints.orientation_euler_deg` into the convert form and submits
    the normal `POST /api/convert` request.

    - **width_mm / depth_mm / height_mm**: model bounding-box dimensions
    - **volume_mm3 / surface_area_mm2**: volumetric geometry features
    - **overhang_ratio**: fraction of surface area classified as overhang (0–1)
    - **thin_wall_ratio**: fraction of surface area with sub-nozzle wall thickness (0–1)
    - **current_rotation**: current model rotation in degrees (default 0, 0, 0)
    """
    try:
        return orientation.suggest(request)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Orientation engine error: {exc}"
        ) from exc
