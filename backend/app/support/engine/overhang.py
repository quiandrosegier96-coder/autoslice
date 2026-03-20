"""
AutoSlice — Tree Support Engine: Overhang Detection

Step 1: Detect mesh triangles that require external support.

A triangle is an overhang candidate when:
  1. Its normal has a significant downward component:
       dot(normal, gravity) > cos(overhang_angle_deg)
  2. Its centroid is above the build plate (not touching the floor).
  3. (Optional) No model geometry exists within layer_height directly below
     the centroid — i.e. the face is genuinely "in the air".

All in 3MF Z-up space.  Gravity = (0, 0, -1).
"""

from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np

from .bvh import BVH
from .models import EngineConfig, OverhangFace, Vec3

# ── Gravity (Z-up) ────────────────────────────────────────────────────────────

_GRAVITY = np.array([0.0, 0.0, -1.0])


# ── Main entry point ──────────────────────────────────────────────────────────

def detect_overhangs(
    vertices:  np.ndarray,   # (N, 3)
    faces:     np.ndarray,   # (M, 3) int
    normals:   np.ndarray,   # (M, 3)  — per-face normals, pre-computed
    config:    EngineConfig,
    floor_z:   float,
    bvh:       BVH,
) -> List[OverhangFace]:
    """
    Return all triangles that need external support.

    Parameters
    ----------
    vertices : (N, 3) mesh vertex array
    faces    : (M, 3) face indices
    normals  : (M, 3) per-face outward normals (unit vectors)
    config   : engine configuration
    floor_z  : Z coordinate of the build plate
    bvh      : pre-built BVH for ray casting
    """
    cos_threshold = math.cos(math.radians(config.overhang_angle_deg))
    floor_cutoff  = floor_z + config.floor_margin_mm

    # ── 1. Vectorised normal filter ───────────────────────────────────────────
    # dot(normal, gravity) = -normal_z (since gravity = (0,0,-1))
    dot_gravity = -(normals[:, 2])                     # shape (M,)
    candidate_mask = dot_gravity > cos_threshold       # True where overhang

    # ── 2. Centroid filter (above floor) ─────────────────────────────────────
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    centroids = (v0 + v1 + v2) / 3.0                  # (M, 3)
    above_floor = centroids[:, 2] > floor_cutoff

    candidate_mask &= above_floor

    candidate_indices = np.where(candidate_mask)[0]

    # ── 3. Per-face area filter (skip degenerate triangles) ───────────────────
    e1_all = v1 - v0
    e2_all = v2 - v0
    cross   = np.cross(e1_all, e2_all)                # (M, 3)
    areas   = np.linalg.norm(cross, axis=1) * 0.5     # (M,)

    candidate_indices = candidate_indices[areas[candidate_indices] >= 0.01]

    # ── 4. (Optional) Ray-cast verification ───────────────────────────────────
    result: List[OverhangFace] = []
    gap    = config.layer_height_mm * 1.5             # self-support threshold

    for fi in candidate_indices:
        centroid = centroids[fi]
        dot_v    = float(dot_gravity[fi])
        area     = float(areas[fi])

        if config.verify_unsupported:
            # Cast ray downward from centroid (offset slightly upward to avoid
            # self-intersection), check if anything is below within gap.
            origin  = centroid + np.array([0.0, 0.0, 0.05])
            max_d   = float(centroid[2] - floor_z)

            hit = bvh.ray_cast(origin, _GRAVITY, max_dist=max_d, skip_face=int(fi))
            if hit is not None and hit[0] < gap:
                continue  # geometry too close below → self-supporting

        normal_v = Vec3(*normals[fi].tolist())
        centroid_v = Vec3(*centroid.tolist())

        result.append(OverhangFace(
            index        = int(fi),
            centroid     = centroid_v,
            normal       = normal_v,
            area         = area,
            overhang_dot = dot_v,
        ))

    return result


# ── Mesh pre-processing helper ────────────────────────────────────────────────

def compute_face_normals(
    vertices: np.ndarray,
    faces:    np.ndarray,
) -> np.ndarray:
    """
    Compute per-face outward normals (unit vectors).

    Returns (M, 3) float array.
    """
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    e1 = v1 - v0
    e2 = v2 - v0
    cross  = np.cross(e1, e2)
    norms  = np.linalg.norm(cross, axis=1, keepdims=True)
    norms  = np.where(norms < 1e-12, 1.0, norms)
    return cross / norms


# ── Support classification helper ─────────────────────────────────────────────

def classify_support_type(
    overhangs: List[OverhangFace],
    config:    EngineConfig,
) -> Tuple[str, str]:
    """
    Decide whether tree or standard supports are more appropriate.

    Returns (support_type, reason).
    """
    if not overhangs:
        return "none", "No unsupported overhang faces detected."

    total_area = sum(f.area for f in overhangs)
    avg_dot    = sum(f.overhang_dot for f in overhangs) / len(overhangs)

    # Compact overhangs → broad single region → standard may be fine
    # Separated clusters with curved normals → tree is better
    # We classify here before clustering; a refined decision is made in the
    # pipeline after clustering.

    if total_area < 50.0:
        return "tree", f"Small overhang area ({total_area:.1f} mm²): tree minimises material."

    if avg_dot > 0.92:
        return "standard", (
            "Overhangs are nearly horizontal flat surfaces; "
            "grid supports provide better area coverage."
        )

    return "tree", (
        f"{len(overhangs)} overhang faces ({total_area:.0f} mm² total) "
        "with varied normals — tree supports reduce scarring."
    )
