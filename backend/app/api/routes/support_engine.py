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

from fastapi import APIRouter, HTTPException, Query

from app.ingestion.handler import find_job
from app.ingestion.unpacker import unpack
from app.geometry.mesh_loader import merge_meshes
from app.parser.model_parser import parse_model_files
from app.support.engine import (
    EngineConfig,
    run_pipeline,
    serialise,
    serialise_skeleton,
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

async def _load_mesh(job_id: str):
    """Load and merge all mesh parts from a 3MF job."""
    job = find_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found.")

    try:
        archive_path = job["archive_path"]
        files        = await asyncio.to_thread(unpack, archive_path)
        model_data   = await asyncio.to_thread(parse_model_files, files)
        mesh         = await asyncio.to_thread(merge_meshes, model_data)
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
) -> Dict[str, Any]:
    """
    Run the full tree support generation engine.

    Returns complete support graph (nodes, segments, clusters, contacts, stats).
    """
    mesh   = await _load_mesh(job_id)
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
) -> Dict[str, Any]:
    """
    Fast skeleton response — segments + stats only.
    Suitable for initial preview before full result loads.
    """
    mesh   = await _load_mesh(job_id)
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


# ── Support decision only ─────────────────────────────────────────────────────

@router.get("/{job_id}/decision")
async def get_support_decision(
    job_id:         str,
    overhang_angle: float = Query(45.0, ge=10.0, le=80.0),
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

    mesh   = await _load_mesh(job_id)
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
