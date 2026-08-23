"""
AutoSlice — Tree Support Engine API Route

GET  /api/support/{job_id}/engine
     Run the full tree support generation pipeline on the uploaded model.
     Returns the complete support graph + stats.

GET  /api/support/{job_id}/engine/skeleton
     Lightweight response: segments + stats only (fast initial preview).

Query parameters
----------------
overhang_angle   float  Overhang threshold in degrees (default 45)
branch_angle     float  Max branch angle from vertical (default 40)
merge_l1         float  L1 merge radius mm (default 15)
merge_l2         float  L2 merge radius mm (default 35)
merge_l3         float  L3 merge radius mm (default 70)
cluster_cell     float  Cluster grid cell size mm (default 5)
z_distance       float  Z gap between tip and surface mm (default 0.2)
tip_radius       float  Tip sphere radius mm (default 0.5)
collision        bool   Enable collision avoidance (default true)
verify_unsupported bool  Ray-cast below each cluster (default true)
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.ingestion.handler import find_owned_job
from app.ingestion.unpacker import unpack
from app.geometry.mesh_loader import merge_meshes
from app.parser.model_parser import parse_model_files
from app.support.engine import (
    EngineConfig,
    run_pipeline,
    serialise,
    serialise_skeleton,
)
from app.support.engine.validator import (
    tag_debug,
    DEFAULT_CLEARANCE_MM as _DEFAULT_CLEARANCE,
)

router = APIRouter(prefix="/api/support", tags=["support-engine"])
log    = logging.getLogger(__name__)


# ── Config builder ────────────────────────────────────────────────────────────

def _build_config(
    overhang_angle:     float,
    branch_angle:       float,
    merge_l1:           float,
    merge_l2:           float,
    merge_l3:           float,
    cluster_cell:       float,
    z_distance:         float,
    tip_radius:         float,
    collision:          bool,
    verify_unsupported: bool,
) -> EngineConfig:
    return EngineConfig(
        overhang_angle_deg          = overhang_angle,
        branch_angle_deg            = branch_angle,
        merge_l1_mm                 = merge_l1,
        merge_l2_mm                 = merge_l2,
        merge_l3_mm                 = merge_l3,
        cluster_cell_mm             = cluster_cell,
        z_distance_mm               = z_distance,
        tip_radius_mm               = tip_radius,
        enable_collision_avoidance  = collision,
        verify_unsupported          = verify_unsupported,
    )


# ── Mesh loader helper ────────────────────────────────────────────────────────

async def _load_mesh(job_id: str, user_id: int):
    """Load and merge all mesh parts from a 3MF job."""
    job = find_owned_job(job_id, user_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found.")

    try:
        archive    = await asyncio.to_thread(unpack, job.archive_path, job.extract_dir)
        model_data = await asyncio.to_thread(
            parse_model_files,
            archive.model_files,
            archive.object_type_map,
        )
        mesh       = await asyncio.to_thread(merge_meshes, model_data.objects)
    except Exception as e:
        log.exception("Mesh load failed for job %s", job_id)
        raise HTTPException(status_code=500, detail=f"Mesh load error: {e}") from e

    if mesh is None or len(mesh.faces) == 0:
        raise HTTPException(status_code=422, detail="No valid mesh geometry found.")

    return mesh


# ── Full engine endpoint ──────────────────────────────────────────────────────

@router.get("/{job_id}/engine")
async def get_tree_support_engine(
    job_id: str,
    overhang_angle:     float = Query(45.0,  ge=10.0, le=80.0),
    branch_angle:       float = Query(40.0,  ge=10.0, le=70.0),
    merge_l1:           float = Query(15.0,  ge=5.0,  le=50.0),
    merge_l2:           float = Query(35.0,  ge=10.0, le=100.0),
    merge_l3:           float = Query(70.0,  ge=20.0, le=200.0),
    cluster_cell:       float = Query(5.0,   ge=1.0,  le=20.0),
    z_distance:         float = Query(0.2,   ge=0.0,  le=2.0),
    tip_radius:         float = Query(0.5,   ge=0.2,  le=3.0),
    collision:          bool  = Query(True),
    verify_unsupported: bool  = Query(True),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Run the full tree support generation engine.

    Returns complete support graph (nodes, segments, clusters, contacts, stats).
    """
    mesh   = await _load_mesh(job_id, int(current_user["sub"]))
    config = _build_config(
        overhang_angle, branch_angle, merge_l1, merge_l2, merge_l3,
        cluster_cell, z_distance, tip_radius, collision, verify_unsupported,
    )

    try:
        plan = await asyncio.to_thread(run_pipeline, mesh, config)
    except Exception as e:
        log.exception("Engine pipeline failed for job %s", job_id)
        raise HTTPException(status_code=500, detail=f"Support engine error: {e}") from e

    return serialise(plan)


# ── Skeleton-only endpoint ────────────────────────────────────────────────────

@router.get("/{job_id}/engine/skeleton")
async def get_tree_support_skeleton(
    job_id:             str,
    overhang_angle:     float = Query(45.0,  ge=10.0, le=80.0),
    branch_angle:       float = Query(40.0,  ge=10.0, le=70.0),
    merge_l1:           float = Query(15.0,  ge=5.0,  le=50.0),
    merge_l2:           float = Query(35.0,  ge=10.0, le=100.0),
    merge_l3:           float = Query(70.0,  ge=20.0, le=200.0),
    cluster_cell:       float = Query(5.0,   ge=1.0,  le=20.0),
    z_distance:         float = Query(0.2,   ge=0.0,  le=2.0),
    tip_radius:         float = Query(0.5,   ge=0.2,  le=3.0),
    collision:          bool  = Query(False),   # skip for speed
    verify_unsupported: bool  = Query(False),   # skip for speed
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Fast skeleton response — segments + stats only.
    Suitable for initial preview before full result loads.
    """
    mesh   = await _load_mesh(job_id, int(current_user["sub"]))
    config = _build_config(
        overhang_angle, branch_angle, merge_l1, merge_l2, merge_l3,
        cluster_cell, z_distance, tip_radius, collision, verify_unsupported,
    )

    try:
        plan = await asyncio.to_thread(run_pipeline, mesh, config)
    except Exception as e:
        log.exception("Skeleton pipeline failed for job %s", job_id)
        raise HTTPException(status_code=500, detail=f"Support engine error: {e}") from e

    return serialise_skeleton(plan)


# ── Debug validation tags ────────────────────────────────────────────────────

@router.get("/{job_id}/engine/debug-tags")
async def get_debug_tags(
    job_id:         str,
    overhang_angle: float = Query(45.0,  ge=10.0, le=80.0),
    clearance:      float = Query(_DEFAULT_CLEARANCE, ge=0.0, le=5.0),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Return per-segment validation tags for debug visualisation:
      "valid"     → GREEN  (passes all checks)
      "colliding" → ORANGE (ray-cast intersection)
      "internal"  → RED    (sample point inside mesh)
      "too_close" → YELLOW (clearance violated)
    """
    mesh = await _load_mesh(job_id, int(current_user["sub"]))
    config = EngineConfig(overhang_angle_deg=overhang_angle)

    try:
        plan = await asyncio.to_thread(run_pipeline, mesh, config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    from app.support.engine.bvh import BVH
    import numpy as np

    bvh = BVH(
        np.asarray(mesh.vertices, dtype=np.float64),
        np.asarray(mesh.faces,    dtype=np.int32),
    )

    tags = tag_debug(
        segments  = plan.segments,
        nodes     = plan.nodes,
        bvh       = bvh,
        mesh_tm   = mesh,
        clearance = clearance,
    )

    colour_map = {
        "valid":     "#00ff88",
        "colliding": "#ff6600",
        "internal":  "#ff2222",
        "too_close": "#ffdd00",
    }

    return {
        "segment_tags": {str(k): v for k, v in tags.items()},
        "colour_map":   colour_map,
        "counts": {tag: sum(1 for v in tags.values() if v == tag)
                   for tag in colour_map},
    }


# ── Support decision only ─────────────────────────────────────────────────────

@router.get("/{job_id}/decision")
async def get_support_decision(
    job_id:         str,
    overhang_angle: float = Query(45.0, ge=10.0, le=80.0),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Lightweight: return only the support type decision (tree/standard/none)
    and basic cluster count. No full tree computation.
    """
    from app.support.engine.bvh       import BVH
    from app.support.engine.overhang  import compute_face_normals, detect_overhangs
    from app.support.engine.clustering import cluster_overhangs
    from app.support.engine           import classify_support_type_refined
    import numpy as np

    mesh   = await _load_mesh(job_id, int(current_user["sub"]))
    config = EngineConfig(overhang_angle_deg=overhang_angle, verify_unsupported=False)

    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces    = np.asarray(mesh.faces, dtype=np.int32)
    normals  = np.asarray(mesh.face_normals, dtype=np.float64)
    floor_z  = float(mesh.bounds[0][2])

    def _run():
        bvh       = BVH(vertices, faces)
        overhangs = detect_overhangs(vertices, faces, normals, config, floor_z, bvh)
        clusters  = cluster_overhangs(overhangs, config)
        stype, reason = classify_support_type_refined(clusters, config)
        return {
            "supportDecision": {
                "type":         stype,
                "reason":       reason,
                "clusterCount": len(clusters),
                "totalAreaMm2": round(sum(c.area for c in clusters), 1),
            }
        }

    try:
        return await asyncio.to_thread(_run)
    except Exception as e:
        log.exception("Decision endpoint failed for job %s", job_id)
        raise HTTPException(status_code=500, detail=str(e)) from e
