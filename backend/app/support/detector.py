"""
AutoSlice — Support preview generator (v3).

Target detection pipeline
─────────────────────────
  1. Face normal filter      dot(n, -Z) > cos(45°)
  2. Floor exclusion         centroid.z > z_min + floor_margin
  3. 3D grid clustering      key = (⌊x/6⌋, ⌊y/6⌋, ⌊z/4⌋)
                              separates stacked overhangs that share XY
  4. Area-weighted centroid  large faces pull position, not small strays
  5. Min area filter         cluster total area ≥ MIN_CLUSTER_AREA_MM2
  6. Inside-mesh filter      test 1 mm below surface (not on it)
  7. Self-support raycast    offset 0.5 mm, skip self-hits < 1 mm,
                              gap = z_top − first_valid_hit
                              gap < 3 mm → already supported → skip

Coordinates are returned in 3MF space (Z-up, mm).  The frontend applies the
same -π/2 X rotation used by ThreeMFLoader, then subtracts model_floor_z to
align with the AutoCamera bottom-alignment transform.
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

# XY cluster resolution — 6 mm keeps column count manageable.
# 3 mm produced one column per 9 mm² → spaghetti on large overhangs.
# 6 mm → one column per 36 mm², ~4× fewer columns before the hard cap.
GRID_CELL_XY_MM = 6.0   # mm — XY cluster resolution
GRID_CELL_Z_MM  = 4.0   # mm — Z cluster resolution (separates stacked layers)

MAX_OVERHANG_TRI = 3000  # cap on triangles sent for visualization
MAX_COLUMNS      = 120   # hard cap; tree-merge further reduces visible trunks

# Ray origin is placed this far below the overhang centroid.
# 0.5 mm reliably clears the source triangle and immediate neighbours.
RAY_OFFSET_MM = 0.5

# Hits within this distance of the ray origin are self-intersection artifacts.
RAY_SELFHIT_MM = 1.0

# Clearance between overhang and nearest geometry directly below it.
# Gap < this → face is already self-supported → skip.
SELF_SUPPORT_GAP_MM = 3.0

# Minimum total overhang area a cluster must represent.
# Area-based (mm²) is more meaningful than face count because mesh
# tessellation density varies — a coarse mesh has fewer but larger faces.
MIN_CLUSTER_AREA_MM2 = 4.0

# Faces whose centroid is within this distance of z_min are treated as
# resting on the build plate and excluded from overhang detection.
FLOOR_MARGIN_RATIO  = 0.02    # fraction of model height
FLOOR_MARGIN_MIN_MM = 0.5     # minimum, mm

# ── Cache (in-process, per uvicorn worker) ────────────────────────────────────

_cache: dict[str, SupportPreviewData] = {}
_CACHE_VERSION = "v6"   # bump this to invalidate all in-process cache entries


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
        return _no_supports(job_id, center, z_min)

    ov_nz        = nz[overhang_mask]
    ov_tris      = face_vertices[overhang_mask]       # (M, 3, 3)
    ov_centroids = face_centroids[overhang_mask]      # (M, 3)
    ov_area      = mesh.area_faces[overhang_mask]     # (M,)

    # ── 3. 3D grid clustering ─────────────────────────────────────────────────
    # Key uses THREE axes — XY for proximity, Z to separate stacked overhangs.
    # Two overhangs at the same XY footprint but different heights (e.g. a
    # bridge at Z=5 and an arm at Z=40) must produce separate targets.
    # IMPORTANT: use math.floor, not int() — int() truncates toward zero,
    # giving asymmetric bins for negative coordinates.
    grid: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    for i, c in enumerate(ov_centroids):
        cell = (
            math.floor(c[0] / GRID_CELL_XY_MM),
            math.floor(c[1] / GRID_CELL_XY_MM),
            math.floor(c[2] / GRID_CELL_Z_MM),
        )
        grid[cell].append(i)

    # ── 4+5. Area-weighted centroid + minimum area filter ─────────────────────
    # Each face contributes to the cluster centroid proportional to its area.
    # Equal-weight mean drifts toward sparse tiny edge-triangles and can land
    # outside the overhang polygon entirely.  Area-weighted mean stays inside.
    clusters: list[dict] = []
    for indices in grid.values():
        face_areas = ov_area[indices]
        total_area = float(face_areas.sum())

        if total_area < MIN_CLUSTER_AREA_MM2:   # Step 5 — min area filter
            continue

        pts = ov_centroids[indices]              # (k, 3)
        w   = face_areas / total_area            # area weights, sum=1

        cx     = float((pts[:, 0] * w).sum())   # area-weighted X
        cy     = float((pts[:, 1] * w).sum())   # area-weighted Y
        z_top  = float(pts[:, 2].min())         # lowest face in cluster = highest risk
        min_nz = float(ov_nz[indices].min())

        clusters.append(dict(
            cx=cx, cy=cy, z_top=z_top,
            area=total_area, min_nz=min_nz,
        ))

    # ── 6. Inside-mesh filter ─────────────────────────────────────────────────
    # Interior downward faces (hollow models, concave cavities) pass the normal
    # filter but a support placed there would float inside the shell.
    #
    # Test point is 1 mm BELOW the surface — not on it.  A point exactly on
    # the mesh boundary is a numerical edge case for winding-number queries;
    # 1 mm below is unambiguously inside any hollow shell of practical thickness.
    if clusters:
        try:
            test_pts    = np.array([[c['cx'], c['cy'], c['z_top'] - 1.0]
                                    for c in clusters])
            inside_mask = mesh.contains(test_pts)
            clusters    = [c for c, ins in zip(clusters, inside_mask) if not ins]
        except Exception:
            pass   # non-watertight mesh — keep all candidates

    if not clusters:
        return _no_supports(job_id, center, z_min)

    # ── 7. Self-support raycast ───────────────────────────────────────────────
    # Origin = 0.5 mm below overhang surface (clears the source face).
    # multiple_hits=True — collect every intersection along the ray.
    # Sort by distance from origin and skip any hit within RAY_SELFHIT_MM
    # (those are self-intersections against the source face or neighbours).
    # The first remaining hit is the closest real geometry below the overhang.
    # gap = z_top − hit.z  (measured from the surface, not the ray origin).
    # gap < SELF_SUPPORT_GAP_MM → already self-supported → skip.
    ray_origins = np.array(
        [[c['cx'], c['cy'], c['z_top'] - RAY_OFFSET_MM] for c in clusters],
        dtype=float,
    )
    ray_dirs = np.tile([0.0, 0.0, -1.0], (len(clusters), 1)).astype(float)

    # first_hit_z[i] = Z of the first valid (non-self) hit for cluster i
    first_hit_z: dict[int, float] = {}
    try:
        locs, idx_ray, _ = mesh.ray.intersects_location(
            ray_origins=ray_origins,
            ray_directions=ray_dirs,
            multiple_hits=True,
        )
        # Group hits by ray index, then sort by distance and pick first valid
        hits_by_ray: dict[int, list[tuple[float, float]]] = defaultdict(list)
        for loc, ri in zip(locs, idx_ray):
            origin_z = float(ray_origins[int(ri)][2])
            hz       = float(loc[2])
            dist     = origin_z - hz          # positive = below origin
            if dist > 0:
                hits_by_ray[int(ri)].append((dist, hz))

        for ri, hit_list in hits_by_ray.items():
            hit_list.sort(key=lambda t: t[0])
            for dist, hz in hit_list:
                if dist >= RAY_SELFHIT_MM:    # skip self-hits
                    first_hit_z[ri] = hz
                    break
    except Exception:
        pass   # ray module unavailable — fall back to z_min for all clusters

    # ── 8. Build support columns ──────────────────────────────────────────────
    columns:              list[SupportColumn] = []
    debug_active_pts:     list[float]         = []
    debug_filtered_pts:   list[float]         = []

    for i, cl in enumerate(clusters):
        z_top = cl['z_top']
        h_hit = first_hit_z.get(i)

        if h_hit is not None:
            gap = z_top - h_hit              # true gap: surface → hit
            if gap < SELF_SUPPORT_GAP_MM:
                if debug:
                    debug_filtered_pts += [cl['cx'], cl['cy'], z_top]
                continue
            z_bottom = h_hit + 0.1
        else:
            z_bottom = z_min                 # open air → column reaches bed

        if z_top - z_bottom < 0.5:
            if debug:
                debug_filtered_pts += [cl['cx'], cl['cy'], z_top]
            continue

        radius = float(min(max(math.sqrt(cl['area']) * 0.35, 0.5), 5.0))
        columns.append(SupportColumn(
            x=cl['cx'], y=cl['cy'],
            z_bottom=z_bottom, z_top=z_top,
            radius=radius,
        ))

        if debug:
            debug_active_pts += [cl['cx'], cl['cy'], z_top]

    if not columns:
        return _no_supports(job_id, center, z_min)

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
        tree_branches = generate_tree_branches(columns_capped, z_min=z_min, mesh=mesh)
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
        model_floor_z=z_min,
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


def _no_supports(job_id: str, center: list[float], floor_z: float = 0.0) -> SupportPreviewData:
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
        model_floor_z=floor_z,
        overhang_area_mm2=0.0,
        column_count=0,
        debug=None,
    )
