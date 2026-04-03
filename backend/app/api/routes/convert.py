"""
AutoSlice — Convert route.
POST /api/convert
  Runs geometry analysis + rules engine + export → returns Anycubic .3mf download.
"""

import asyncio
import dataclasses
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import numpy as np

from app.ingestion.handler import find_job
from app.ingestion.unpacker import unpack
from app.parser.model_parser import parse_model_files
from app.auth.dependencies import get_optional_user
from app.database import log_job, log_generation_v2
from app.diagnostics.models import DecisionTrace
from app.geometry.analyzer import analyze_mesh
from app.geometry.mesh_loader import merge_meshes
from app.normalization.intent import normalize
from app.rules.base_profiles import load_base_profile
from app.rules.engine import generate_settings
from app.rules.printer_loader import load_printer_profile
from app.export.anycubic_exporter import export as do_export
from app.export.mesh_transform import euler_deg_to_rotation_matrix
from app.models.printer import FilamentType

router = APIRouter()


class ConvertRequest(BaseModel):
    job_id: str
    printer_id: str
    filament_type: FilamentType
    nozzle_size_mm: float = 0.4
    nozzle_type: str = "brass"
    filament_diameter_mm: float = 1.75
    build_plate: str = "smooth"
    flush_volume_mm3: float = 3.0
    color_count: int = 1
    filament_colors: list[str] = []
    filament_types: list[str] = []
    orientation_euler_deg: list[float] = []   # [rx, ry, rz] — empty = no rotation


@router.post("/convert")
async def convert(
    req: ConvertRequest,
    current_user: dict | None = Depends(get_optional_user),
):
    job = find_job(req.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{req.job_id}' not found.")

    try:
        printer = load_printer_profile(req.printer_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if req.filament_type not in printer.supported_filaments:
        raise HTTPException(
            status_code=400,
            detail=f"{req.filament_type.value.upper()} is not supported by {printer.display_name}.",
        )

    loop = asyncio.get_event_loop()

    archive = await loop.run_in_executor(None, unpack, job.archive_path, job.extract_dir)
    if not archive.model_files:
        raise HTTPException(status_code=422, detail="No model files found in archive.")

    try:
        parsed_model = await loop.run_in_executor(None, parse_model_files, archive.model_files, archive.object_type_map)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Parse failed: {exc}")

    if not parsed_model.objects:
        raise HTTPException(status_code=422, detail="No mesh objects found.")

    # Determine orientation rotation matrix (None = identity = no rotation)
    rotation_matrix: np.ndarray | None = None
    euler = req.orientation_euler_deg
    if len(euler) == 3 and any(abs(v) > 0.5 for v in euler):
        rotation_matrix = euler_deg_to_rotation_matrix(euler[0], euler[1], euler[2])

    try:
        mesh = await loop.run_in_executor(None, merge_meshes, parsed_model.objects)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to load mesh: {exc}")

    # If rotation requested, apply it to the merged mesh so geometry analysis
    # and settings generation are correct for the rotated orientation
    if rotation_matrix is not None:
        try:
            import trimesh as _trimesh
            rot_4x4 = np.eye(4)
            rot_4x4[:3, :3] = rotation_matrix
            mesh = mesh.copy()
            mesh.apply_transform(rot_4x4)
            # Translate to build plate (Z_min = 0)
            z_min = float(mesh.bounds[0][2])
            if abs(z_min) > 0.001:
                mesh.apply_translation([0.0, 0.0, -z_min])
        except Exception:
            rotation_matrix = None  # rotation failed — continue with original

    try:
        geometry = await loop.run_in_executor(
            None, analyze_mesh, mesh, len(parsed_model.objects)
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Geometry analysis failed: {exc}")

    # Apply user's nozzle size to the printer profile before rules engine
    printer.nozzle_diameter_mm = req.nozzle_size_mm

    try:
        intent = normalize(geometry)

        # Capture base settings for delta calculation
        base_settings_json = json.dumps(dataclasses.asdict(load_base_profile(printer)))

        # Run engine with decision trace
        trace = DecisionTrace(
            job_id     = req.job_id,
            printer_id = req.printer_id,
            filament   = req.filament_type.value,
            nozzle_mm  = req.nozzle_size_mm,
        )
        print_settings = generate_settings(intent, printer, req.filament_type, req.nozzle_size_mm, trace)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Settings generation failed: {exc}")

    # Store hardware selections in settings for export
    print_settings.nozzle_size_mm      = req.nozzle_size_mm
    print_settings.nozzle_type         = req.nozzle_type
    print_settings.filament_diameter_mm = req.filament_diameter_mm
    print_settings.build_plate         = req.build_plate
    print_settings.flush_volume_mm3    = req.flush_volume_mm3
    print_settings.color_count         = min(req.color_count, printer.max_colors)
    print_settings.filament_colors     = req.filament_colors
    print_settings.filament_types      = req.filament_types

    # Adjust bed temperature based on build plate type
    _VALID_PLATES = {"smooth", "textured", "cold", "high_temp", "glass"}
    effective_plate = req.build_plate if req.build_plate in _VALID_PLATES else "smooth"
    if effective_plate != req.build_plate:
        # Stale/unknown plate value — normalise silently
        print_settings.build_plate = effective_plate

    if effective_plate == "textured":
        print_settings.bed_temp_c = min(print_settings.bed_temp_c + 5, 120)
    elif effective_plate == "cold":
        print_settings.bed_temp_c = 0
    elif effective_plate == "high_temp":
        print_settings.bed_temp_c = min(print_settings.bed_temp_c + 10, 130)

    output_filename = f"autoslice_{req.printer_id}_{req.filament_type.value}.3mf"
    output_path = job.archive_path.parent / output_filename

    try:
        await loop.run_in_executor(
            None, do_export, archive, print_settings, printer,
            req.filament_type, output_path, rotation_matrix, parsed_model,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}")

    user_id = int(current_user["sub"]) if current_user else None
    log_job(req.job_id, user_id, "convert",
            filename=job.original_filename, printer_id=req.printer_id)

    try:
        log_generation_v2(
            job_id             = req.job_id,
            printer_id         = req.printer_id,
            filament_type      = req.filament_type.value,
            nozzle_size_mm     = req.nozzle_size_mm,
            geometry           = geometry,
            intent             = intent,
            settings_json      = json.dumps(dataclasses.asdict(print_settings)),
            base_settings_json = base_settings_json,
            trace              = trace,
        )
    except Exception:
        pass  # logging failure must never break the response

    return FileResponse(
        path=str(output_path),
        media_type="application/zip",
        filename=output_filename,
    )
