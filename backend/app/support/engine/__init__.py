"""
AutoSlice — Tree Support Engine: Pipeline Orchestrator

Full pipeline:
  1. Mesh preprocessing     — build BVH, compute normals, find floor Z
  2. Overhang detection     — normal filter + optional ray-cast verification
  3. Spatial clustering     — grid Union-Find → connected overhang islands
  4. Support-type decision  — tree vs. standard vs. none
  5. Path planning          — 3-level hierarchical tree construction
  6. Collision avoidance    — ray-cast per segment, insert waypoints
  7. Graph optimisation     — feature enforcement, pruning, reinforcement
  8. Serialisation          — JSON-ready output dict

Usage
-----
    from app.support.engine import run_pipeline, EngineConfig

    plan   = run_pipeline(trimesh_mesh, EngineConfig())
    result = serialise(plan)   # dict ready for JSON response
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np

try:
    import trimesh as _trimesh
    _HAS_TRIMESH = True
except ImportError:
    _HAS_TRIMESH = False

from .bvh        import BVH
from .collision  import avoid_collisions
from .clustering import cluster_overhangs
from .models     import EngineConfig, SupportStats, TreeSupportPlan
from .optimizer  import optimize
from .overhang   import classify_support_type, compute_face_normals, detect_overhangs
from .planner    import plan_tree
from .serializer import compute_stats, serialise, serialise_skeleton
from .validator  import filter_valid_segments

log = logging.getLogger(__name__)

__all__ = [
    "run_pipeline",
    "run_pipeline_from_arrays",
    "EngineConfig",
    "TreeSupportPlan",
    "serialise",
    "serialise_skeleton",
]


# ── Main entry (trimesh mesh) ─────────────────────────────────────────────────

def run_pipeline(
    mesh:   "Any",            # trimesh.Trimesh
    config: Optional[EngineConfig] = None,
) -> TreeSupportPlan:
    """
    Run the full tree support engine on a trimesh.Trimesh object.

    Parameters
    ----------
    mesh   : trimesh.Trimesh (Z-up, mm units)
    config : EngineConfig, or None for defaults

    Returns
    -------
    TreeSupportPlan
    """
    cfg = config or EngineConfig()

    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces    = np.asarray(mesh.faces,    dtype=np.int32)

    # Pre-computed trimesh normals are correct and cheaper than recomputing
    if hasattr(mesh, "face_normals"):
        normals = np.asarray(mesh.face_normals, dtype=np.float64)
    else:
        normals = compute_face_normals(vertices, faces)

    floor_z     = float(mesh.bounds[0][2])
    bbox_center = mesh.bounding_box.centroid

    return run_pipeline_from_arrays(
        vertices    = vertices,
        faces       = faces,
        normals     = normals,
        floor_z     = floor_z,
        bbox_center = bbox_center,
        config      = cfg,
        mesh_tm     = mesh,          # pass trimesh object for strict validation
    )


# ── Main entry (raw arrays) ───────────────────────────────────────────────────

def run_pipeline_from_arrays(
    vertices:    np.ndarray,
    faces:       np.ndarray,
    normals:     np.ndarray,
    floor_z:     float,
    bbox_center: np.ndarray,
    config:      Optional[EngineConfig] = None,
    mesh_tm:     "Any" = None,
) -> TreeSupportPlan:
    """
    Run the full pipeline from raw numpy arrays.

    Coordinates must be in 3MF Z-up space (mm).
    """
    cfg      = config or EngineConfig()
    warnings = []

    log.debug("Engine: building BVH (%d faces)…", len(faces))

    # ── Step 1: BVH ──────────────────────────────────────────────────────────
    bvh = BVH(vertices, faces, leaf_max=8)

    # ── Step 2: Overhang detection ────────────────────────────────────────────
    log.debug("Engine: detecting overhangs…")
    overhangs = detect_overhangs(vertices, faces, normals, cfg, floor_z, bvh,
                                 mesh_tm=mesh_tm)

    if not overhangs:
        log.debug("Engine: no overhangs — returning empty plan.")
        return _empty_plan("No overhang faces detected.")

    # ── Step 3: Clustering ────────────────────────────────────────────────────
    log.debug("Engine: clustering %d overhang faces…", len(overhangs))
    clusters = cluster_overhangs(overhangs, cfg)

    if not clusters:
        return _empty_plan("No significant overhang clusters (all below area threshold).")

    # ── Step 4: Support type decision ─────────────────────────────────────────
    support_type, reason = classify_support_type_refined(clusters, cfg)

    if support_type == "none":
        return _empty_plan(reason)

    # ── Step 5: Path planning ─────────────────────────────────────────────────
    log.debug("Engine: planning tree for %d clusters…", len(clusters))
    nodes, segments, contacts = plan_tree(clusters, cfg, floor_z)

    # ── Step 6: Collision avoidance ───────────────────────────────────────────
    if cfg.enable_collision_avoidance and nodes and segments:
        log.debug("Engine: collision avoidance (%d segments)…", len(segments))
        nodes, segments = avoid_collisions(nodes, segments, bvh, bbox_center, cfg)

    # ── Step 7: Optimisation ─────────────────────────────────────────────────
    log.debug("Engine: optimising graph…")
    nodes, segments = optimize(nodes, segments, cfg, warnings)

    # ── Step 7b: STRICT VALIDATION (zero tolerance) ───────────────────────────
    # Hard-reject any segment that intersects the mesh, passes through the
    # mesh interior, or violates minimum clearance.
    # We NEVER fix or offset — if a segment is invalid it is simply removed.
    if mesh_tm is not None and segments:
        log.debug("Engine: strict segment validation (%d segments)…", len(segments))
        from .validator import filter_valid_segments, DEFAULT_CLEARANCE_MM
        nodes, segments = filter_valid_segments(
            segments  = segments,
            nodes     = nodes,
            bvh       = bvh,
            mesh_tm   = mesh_tm,
            clearance = cfg.validation_clearance_mm
                        if hasattr(cfg, "validation_clearance_mm")
                        else DEFAULT_CLEARANCE_MM,
        )
        log.debug("Engine: after validation — %d nodes, %d segments.",
                  len(nodes), len(segments))

    # ── Step 8: Build plan ────────────────────────────────────────────────────
    plan = TreeSupportPlan(
        support_type    = support_type,
        decision_reason = reason,
        clusters        = clusters,
        nodes           = nodes,
        segments        = segments,
        contacts        = contacts,
        stats           = SupportStats(0, 0, 0, 0, 0, 0, 0, 0.0),  # recomputed below
        warnings        = warnings,
    )
    plan.stats = compute_stats(plan)

    log.debug(
        "Engine: done — %d nodes, %d segments, %d contacts.",
        len(nodes), len(segments), len(contacts),
    )
    return plan


# ── Refined support-type decision ─────────────────────────────────────────────

def classify_support_type_refined(clusters, cfg: EngineConfig):
    """
    After clustering, make a more informed support-type decision.
    """
    n = len(clusters)

    if n == 0:
        return "none", "No significant overhang regions."

    total_area = sum(c.area for c in clusters)
    max_area   = max(c.area for c in clusters)
    avg_area   = total_area / n

    # Large single region with low Z variation → standard grid may suit
    if n == 1 and total_area > 500.0:
        return (
            "standard",
            f"Single large overhang ({total_area:.0f} mm²): "
            "grid supports provide more even area coverage.",
        )

    # Many isolated small islands → tree excels
    if n >= 3 and avg_area < 150.0:
        return (
            "tree",
            f"{n} isolated overhang islands (avg {avg_area:.0f} mm² each): "
            "tree supports reduce material and surface contact.",
        )

    if n >= 2:
        return (
            "tree",
            f"{n} overhang regions ({total_area:.0f} mm² total): "
            "tree branching allows efficient shared trunk paths.",
        )

    return (
        "tree",
        f"Overhang area {total_area:.0f} mm² with complex geometry — "
        "tree supports minimise scarring.",
    )


# ── Empty plan helper ─────────────────────────────────────────────────────────

def _empty_plan(reason: str) -> TreeSupportPlan:
    return TreeSupportPlan(
        support_type    = "none",
        decision_reason = reason,
        clusters        = [],
        nodes           = [],
        segments        = [],
        contacts        = [],
        stats           = SupportStats(0, 0, 0, 0, 0, 0, 0, 0.0),
        warnings        = [],
    )
