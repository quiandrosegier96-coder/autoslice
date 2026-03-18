"""
AutoSlice — Support preview generator (v2).

Key improvements over v1:
  1. Floor exclusion — faces whose centroid is within floor_margin of z_min are
     not overhangs that need support; they are resting on the build plate.
  2. Corrected grid-cell math — uses math.floor() instead of int(), so negative
     XY coordinates (very common — model centered at origin) bin correctly.
  3. Cluster-first, raycast-per-cluster — avoids per-triangle ray cost while
     still producing geometrically correct results.
  4. Raycast-derived z_bottom — each column's base comes from the highest
     geometry intersected below its footprint, NOT always z=0.  Columns no
     longer pass through solid model geometry.
  5. Self-support gap filter — if existing geometry is within SELF_SUPPORT_GAP_MM
     directly below the overhang, no column is emitted (face is already supported).
  6. Debug layer output — active/filtered candidate points are optionally
     attached to the response when debug=True is requested.

Coordinates are returned in 3MF space (Z-up, mm).  The frontend applies the
same -π/2 X rotation used by ThreeMFLoader, then subtracts model_center to
align with the AutoCamera centering transform.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Optional

import numpy as np
import trimesh

from app.support.models import SupportColumn, SupportDebugLayers, SupportPreviewData, TreeBranch
from app.support.tree_generator import generate_tree_branches

# ── Constants ─────────────────────────────────────────────────────────────────

_COS_45 = math.cos(math.radians(45.0))   # 0.7071  overhang threshold
_COS_55 = math.cos(math.radians(55.0))   # 0.5736  mild / moderate boundary
_COS_65 = math.cos(math.radians(65.0))   # 0.4226  moderate / severe boundary

# XY cluster resolution — 3 mm is a good trade-off between column count and
# spatial accuracy.  2 mm generates too many thin columns; 5 mm merges regions
# that should stay separate.
GRID_CELL_MM = 3.0

MAX_OVERHANG_TRI     = 3000   # cap on triangles sent for visualization
MAX_COLUMNS          = 300    # with raycasting each column is more meaningful

# Offset ray origin slightly below the overhang centroid so the ray does not
# self-intersect the face it started on.
RAY_OFFSET_MM = 0.05

# If existing geometry is within this gap below an overhang centroid, the face
# is considered already supported and no column is generated.
SELF_SUPPORT_GAP_MM = 1.0

# Faces whose centroid is within this distance of z_min are treated as
# resting on the build plate and excluded from overhang detection.
FLOOR_MARGIN_RATIO  = 0.02    # fraction of model height
FLOOR_MARGIN_MIN_MM = 0.5     # minimum, mm

# ── Cache (in-process, per uvicorn worker) ────────────────────────────────────

_cache: dict[str, SupportPreviewData] = {}
_CACHE_VERSION = "v3"   # bump this to invalidate all in-process cache entries


def get_support_preview(
    job_id: str,
    mesh: trimesh.Trimesh,
    debug: bool = False,
) -> SupportPreviewData:
    """Return cached or freshly computed support preview for this job."""
    cache_key = f"{job_id}_{_CACHE_VERSION}{'_dbg' if debug else ''}"
    if cache_key in _cache:
        return _cache[cache_key]
    result = _compute(job_id, mesh, debug=debug)
    _cache[cache_key] = result
    return result


def invalidate(job_id: str) -> None:
    """Remove all cached variants for this job (call when the mesh changes)."""
    for k in (job_id, f"{job_id}_dbg"):
        _cache.pop(k, None)


# ── Core computation ──────────────────────────────────────────────────────────

def _compute(
    job_id: str,
    mesh: trimesh.Trimesh,
    *,
    debug: bool = False,
) -> SupportPreviewData:

    # ── Bounding box ──────────────────────────────────────────────────────────
    bb     = mesh.bounding_box.bounds      # [[xmin,ymin,zmin],[xmax,ymax,zmax]]
    center = ((bb[0] + bb[1]) / 2).tolist()
    z_min  = float(bb[0][2])
    z_max  = float(bb[1][2])

    # ── 1. Floor margin ───────────────────────────────────────────────────────
    # Faces at or very near z_min are the model's contact surface with the build
    # plate.  They have downward normals but need no support.
    floor_margin = max((z_max - z_min) * FLOOR_MARGIN_RATIO, FLOOR_MARGIN_MIN_MM)
    floor_z      = z_min + floor_margin

    # ── 2. Overhang face detection ────────────────────────────────────────────
    face_normals   = mesh.face_normals             # (F, 3)
    face_vertices  = mesh.triangles                # (F, 3, 3)
    face_centroids = mesh.triangles.mean(axis=1)   # (F, 3)  centroid per face
    nz             = face_normals[:, 2]

    # Downward-facing AND above the floor zone
    overhang_mask = (nz < -_COS_45) & (face_centroids[:, 2] > floor_z)

    if not overhang_mask.any():
        return _no_supports(job_id, center)

    ov_nz        = nz[overhang_mask]
    ov_tris      = face_vertices[overhang_mask]       # (M, 3, 3)
    ov_centroids = face_centroids[overhang_mask]      # (M, 3)
    ov_area      = mesh.area_faces[overhang_mask]

    # ── 3. XY grid clustering ─────────────────────────────────────────────────
    # IMPORTANT: use math.floor, not int().
    # int() truncates toward zero, giving asymmetric bins for negative values.
    # E.g. int(-3.5/3) = int(-1.16) = -1 but int(-6.5/3) = int(-2.16) = -2,
    # while floor(-3.5/3) = floor(-1.16) = -2 (correct bin for negative side).
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, c in enumerate(ov_centroids):
        cell = (
            math.floor(c[0] / GRID_CELL_MM),
            math.floor(c[1] / GRID_CELL_MM),
        )
        grid[cell].append(i)

    # One candidate dict per cluster
    clusters: list[dict] = []
    for indices in grid.values():
        pts    = ov_centroids[indices]              # (k, 3)
        cx     = float(pts[:, 0].mean())
        cy     = float(pts[:, 1].mean())
        z_top  = float(pts[:, 2].min())            # lowest overhang in this XY cell
        count  = len(indices)
        min_nz = float(ov_nz[indices].min())
        clusters.append(dict(cx=cx, cy=cy, z_top=z_top, count=count, min_nz=min_nz))

    # ── 4. Downward raycasting — one ray per cluster ──────────────────────────
    # Each ray origin is placed RAY_OFFSET_MM below the cluster's lowest
    # overhang point.  The offset prevents the ray from self-intersecting the
    # very face whose centroid we computed the origin from.
    #
    # We use multiple_hits=True and then select the HIGHEST hit Z that is
    # strictly below the origin.  This correctly handles concave geometry where
    # the nearest hit going downward might otherwise be on the model's outer
    # shell above an internal cavity.
    n  = len(clusters)
    ray_origins = np.array(
        [[c['cx'], c['cy'], c['z_top'] - RAY_OFFSET_MM] for c in clusters],
        dtype=float,
    )
    ray_dirs = np.tile([0.0, 0.0, -1.0], (n, 1)).astype(float)

    # hit_z[i] = highest geometry Z hit by cluster i's ray (below the origin)
    hit_z: dict[int, float] = {}
    try:
        locs, idx_ray, _ = mesh.ray.intersects_location(
            ray_origins=ray_origins,
            ray_directions=ray_dirs,
            multiple_hits=True,
        )
        for loc, ri in zip(locs, idx_ray):
            hz       = float(loc[2])
            origin_z = float(ray_origins[ri][2])
            if hz < origin_z:                       # hit is below the ray origin
                prev = hit_z.get(int(ri))
                if prev is None or hz > prev:       # keep the HIGHEST hit
                    hit_z[int(ri)] = hz
    except Exception:
        # Ray module unavailable or mesh degeneracy — fall back to z_min for all
        pass

    # ── 5. Build support columns ──────────────────────────────────────────────
    columns:              list[SupportColumn] = []
    debug_active_pts:     list[float]         = []
    debug_filtered_pts:   list[float]         = []

    for i, cl in enumerate(clusters):
        z_top = cl['z_top']
        h_hit = hit_z.get(i)

        if h_hit is not None:
            # Gap between the overhang and the nearest geometry below it
            gap = (z_top - RAY_OFFSET_MM) - h_hit
            if gap < SELF_SUPPORT_GAP_MM:
                # Close enough — existing geometry supports this face
                if debug:
                    debug_filtered_pts += [cl['cx'], cl['cy'], z_top]
                continue
            z_bottom = h_hit + 0.1   # start column just above the hit surface
        else:
            # Nothing detected below — column goes all the way to the build plate
            z_bottom = z_min

        height = z_top - z_bottom
        if height < 0.5:
            # Column would be negligibly short
            if debug:
                debug_filtered_pts += [cl['cx'], cl['cy'], z_top]
            continue

        radius = float(min(max(math.sqrt(cl['count']) * 0.8, 0.5), 6.0))
        columns.append(SupportColumn(
            x=cl['cx'], y=cl['cy'],
            z_bottom=z_bottom, z_top=z_top,
            radius=radius,
        ))

        if debug:
            debug_active_pts += [cl['cx'], cl['cy'], z_top]

    if not columns:
        return _no_supports(job_id, center)

    # ── 6. Visualization triangles ────────────────────────────────────────────
    # Sort by severity (most severe = most negative nz first), cap at limit.
    order              = np.argsort(ov_nz)[:MAX_OVERHANG_TRI]
    ov_tris_vis        = ov_tris[order]
    severity           = _classify_severity(ov_nz[order])
    overhang_positions = ov_tris_vis.flatten().tolist()

    # ── 7. Metadata ───────────────────────────────────────────────────────────
    severe_ratio   = float((ov_nz <= -_COS_65).sum()) / max(len(ov_nz), 1)
    overhang_ratio = float(overhang_mask.sum()) / max(len(face_normals), 1)
    # Always classify as "tree" — the viewer always renders the branching skeleton.
    # Legacy "normal" label is kept for models with very simple geometry (≤2 columns).
    support_type   = "normal" if len(columns) <= 2 else "tree"
    placement      = "everywhere"  if overhang_ratio > 0.15 else "buildplate_only"
    overhang_area  = float(ov_area.sum())

    columns.sort(key=lambda c: c.radius, reverse=True)

    # ── 7b. Tree support skeleton ─────────────────────────────────────────────
    # Always generate — even "normal" models get a skeleton so the frontend can
    # render branch geometry instead of cylinders whenever possible.
    columns_capped = columns[:MAX_COLUMNS]
    tree_branches: list = []
    try:
        tree_branches = generate_tree_branches(columns_capped, z_min=z_min)
    except Exception:
        tree_branches = []

    trunk_count = sum(1 for b in tree_branches if b.parent_id is None)
    tip_count   = sum(1 for b in tree_branches if b.is_tip)

    # ── 8. Optional debug layers ──────────────────────────────────────────────
    debug_obj: Optional[SupportDebugLayers] = None
    if debug:
        debug_obj = SupportDebugLayers(
            # All detected overhang triangles, uncapped — lets the viewer show
            # what the algorithm sees vs what columns were actually placed.
            all_overhang_positions=ov_tris.flatten().tolist(),
            active_candidate_points=debug_active_pts,
            filtered_candidate_points=debug_filtered_pts,
        )

    return SupportPreviewData(
        job_id=job_id,
        needs_supports=True,
        support_type=support_type,
        placement=placement,
        overhang_positions=overhang_positions,
        overhang_severity=severity,
        support_columns=columns_capped,
        tree_branches=tree_branches,
        trunk_count=trunk_count,
        tip_count=tip_count,
        model_center=center,
        overhang_area_mm2=overhang_area,
        column_count=len(columns_capped),
        debug=debug_obj,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _classify_severity(nz_values: np.ndarray) -> list[str]:
    out: list[str] = []
    for nz in nz_values:
        if nz <= -_COS_65:
            out.append("severe")
        elif nz <= -_COS_55:
            out.append("moderate")
        else:
            out.append("mild")
    return out


def _no_supports(job_id: str, center: list[float]) -> SupportPreviewData:
    return SupportPreviewData(
        job_id=job_id,
        needs_supports=False,
        support_type="none",
        placement="buildplate_only",
        overhang_positions=[],
        overhang_severity=[],
        support_columns=[],
        tree_branches=[],
        trunk_count=0,
        tip_count=0,
        model_center=center,
        overhang_area_mm2=0.0,
        column_count=0,
        debug=None,
    )
