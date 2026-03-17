"""
AutoSlice — Support preview generator.

Loads a merged trimesh, detects overhang faces by normal angle,
clusters them into support column footprints, and returns a
SupportPreviewData payload ready for the Three.js viewer.

Coordinates are returned in 3MF space (Z-up, mm). The frontend
applies the same -π/2 X rotation that ThreeMFLoader uses, then
subtracts the model_center to align with the centered model.
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
import trimesh

from app.support.models import SupportColumn, SupportPreviewData

# ── Thresholds ────────────────────────────────────────────────────────────────

_OVERHANG_DEG = 45.0
_COS_45 = math.cos(math.radians(45.0))   # 0.7071  — overhang threshold
_COS_55 = math.cos(math.radians(55.0))   # 0.5736  — mild/moderate boundary
_COS_65 = math.cos(math.radians(65.0))   # 0.4226  — moderate/severe boundary

GRID_CELL_MM     = 2.0    # XY cluster resolution for column footprints
MAX_OVERHANG_TRI = 3000   # cap triangles sent to avoid large payloads
MAX_COLUMNS      = 500

# ── In-process cache (per worker) ────────────────────────────────────────────

_cache: dict[str, SupportPreviewData] = {}


def get_support_preview(
    job_id: str,
    mesh: trimesh.Trimesh,
) -> SupportPreviewData:
    """Return cached or freshly computed support preview for this job."""
    if job_id in _cache:
        return _cache[job_id]
    result = _compute(job_id, mesh)
    _cache[job_id] = result
    return result


def invalidate(job_id: str) -> None:
    """Remove cached entry (call if the job's mesh changes)."""
    _cache.pop(job_id, None)


# ── Core computation ──────────────────────────────────────────────────────────

def _compute(job_id: str, mesh: trimesh.Trimesh) -> SupportPreviewData:
    # Bounding-box center — used by the frontend to align with AutoCamera centering
    bb     = mesh.bounding_box.bounds      # [[xmin,ymin,zmin], [xmax,ymax,zmax]]
    center = ((bb[0] + bb[1]) / 2).tolist()

    face_normals  = mesh.face_normals      # (F, 3)
    face_vertices = mesh.triangles         # (F, 3, 3) — each face: 3 verts × xyz

    # 1. Identify overhang faces: normal Z < -cos(45°) means face points downward
    nz            = face_normals[:, 2]
    overhang_mask = nz < -_COS_45

    if not overhang_mask.any():
        return _no_supports(job_id, center)

    ov_nz   = nz[overhang_mask]
    ov_tris = face_vertices[overhang_mask]   # (M, 3, 3)

    # 2. Classify severity
    severity = _classify_severity(ov_nz)     # list[str] length M

    # 3. Sort by severity (most negative nz = most severe) and cap
    order    = np.argsort(ov_nz)[:MAX_OVERHANG_TRI]
    ov_tris  = ov_tris[order]
    severity = [severity[i] for i in order]

    # Flatten to [x1,y1,z1, x2,y2,z2, x3,y3,z3, ...] for BufferGeometry
    overhang_positions = ov_tris.flatten().tolist()

    # 4. Cluster all overhang face centroids into support column footprints
    all_centroids = face_vertices[overhang_mask].mean(axis=1)   # (M, 3)
    columns       = _cluster_columns(all_centroids)

    # 5. Derive support type and placement from geometry
    severe_ratio   = float((ov_nz <= -_COS_65).sum()) / max(len(ov_nz), 1)
    overhang_ratio = overhang_mask.sum() / max(len(face_normals), 1)
    support_type   = "tree" if (severe_ratio > 0.05 or overhang_ratio > 0.10) else "normal"
    placement      = "everywhere" if overhang_ratio > 0.15 else "buildplate_only"

    # 6. Overhang area
    overhang_area = float(mesh.area_faces[overhang_mask].sum())

    return SupportPreviewData(
        job_id=job_id,
        needs_supports=True,
        support_type=support_type,
        placement=placement,
        overhang_positions=overhang_positions,
        overhang_severity=severity,
        support_columns=columns,
        model_center=center,
        overhang_area_mm2=overhang_area,
        column_count=len(columns),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _classify_severity(nz_values: np.ndarray) -> list[str]:
    out = []
    for nz in nz_values:
        if nz <= -_COS_65:
            out.append("severe")
        elif nz <= -_COS_55:
            out.append("moderate")
        else:
            out.append("mild")
    return out


def _cluster_columns(centroids: np.ndarray) -> list[SupportColumn]:
    """
    Grid-bin overhang face centroids by XY, one column per cell.
    Each column spans from z=0 (build plate) to the lowest overhang in that cell.
    """
    if len(centroids) == 0:
        return []

    grid: dict[tuple[int, int], list[np.ndarray]] = defaultdict(list)
    for c in centroids:
        cell = (int(c[0] / GRID_CELL_MM), int(c[1] / GRID_CELL_MM))
        grid[cell].append(c)

    columns: list[SupportColumn] = []
    for pts_list in grid.values():
        pts    = np.array(pts_list)
        cx, cy = float(pts[:, 0].mean()), float(pts[:, 1].mean())
        z_top  = float(pts[:, 2].min())
        radius = float(min(max(math.sqrt(len(pts)) * 0.8, 0.5), 8.0))
        columns.append(SupportColumn(
            x=cx, y=cy,
            z_bottom=0.0,
            z_top=z_top,
            radius=radius,
        ))

    columns.sort(key=lambda c: c.radius, reverse=True)
    return columns[:MAX_COLUMNS]


def _no_supports(job_id: str, center: list[float]) -> SupportPreviewData:
    return SupportPreviewData(
        job_id=job_id,
        needs_supports=False,
        support_type="none",
        placement="buildplate_only",
        overhang_positions=[],
        overhang_severity=[],
        support_columns=[],
        model_center=center,
        overhang_area_mm2=0.0,
        column_count=0,
    )
