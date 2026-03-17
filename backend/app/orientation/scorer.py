"""
AutoSlice — Orientation optimizer.

score_orientations(mesh) → OrientationReport

Evaluates 6 principal-axis orientations (the 6 faces of the bounding box on
the build plate) and recommends the best one.

Strategy
--------
Rather than copying the mesh 6 times, we rotate face normals, face centroids,
and vertices in-place using pure numpy matrix multiplication. This is O(N) per
candidate with minimal memory overhead.

Scoring weights
---------------
  support   40%  — overhang area reduction is the highest-value improvement
  adhesion  30%  — contact area determines whether a brim can even grip
  stability 20%  — HBR-based; tall narrow orientations cause tip-over risk
  height    10%  — shorter prints save time and reduce mid-print failure chance

A rotation is only recommended if the best candidate scores >= 10 points
above the original orientation (avoids spurious recommendations on already
well-oriented models).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import trimesh

from app.orientation.models import OrientationCandidate, OrientationReport


# ─────────────────────────────────────────────────────────────────────────────
# Candidate rotation definitions
# Each entry: (angle_rad, axis_unit_vector, label, [rx_deg, ry_deg, rz_deg])
# The original is always index 0 (identity).
# ─────────────────────────────────────────────────────────────────────────────

_CANDIDATES: list[tuple[float, list[float], str, list[float]]] = [
    (0.0,              [1.0, 0.0, 0.0], "Original",       [0,    0,  0]),
    (math.pi,          [1.0, 0.0, 0.0], "Flip (X+180°)",  [180,  0,  0]),
    (math.pi / 2,      [1.0, 0.0, 0.0], "Side (X+90°)",   [90,   0,  0]),
    (-math.pi / 2,     [1.0, 0.0, 0.0], "Side (X-90°)",   [-90,  0,  0]),
    (math.pi / 2,      [0.0, 1.0, 0.0], "Side (Y+90°)",   [0,   90,  0]),
    (-math.pi / 2,     [0.0, 1.0, 0.0], "Side (Y-90°)",   [0,  -90,  0]),
]

# Overhang threshold cosines (same thresholds as overhang.py)
_COS_MILD     = -math.cos(math.radians(45))   # ≈ -0.707
_COS_MODERATE = -math.cos(math.radians(55))   # ≈ -0.574
_COS_SEVERE   = -math.cos(math.radians(65))   # ≈ -0.423


@dataclass
class _RawMetrics:
    """Raw geometry metrics for one candidate — computed without total_score."""
    label:               str
    rotation_euler_deg:  list[float]
    overhang_area_ratio: float
    contact_area_mm2:    float
    height_to_base_ratio: float
    height_mm:           float
    support_score:       int
    adhesion_score:      int
    stability_score:     int


def score_orientations(mesh: trimesh.Trimesh) -> OrientationReport:
    """
    Evaluate all candidate orientations and return the best one with
    a full comparison against the original.
    """
    # Pre-compute mesh arrays once (read-only views — no copy needed)
    normals   = mesh.face_normals       # (N, 3) float64
    areas     = mesh.area_faces         # (N,)   float64
    centroids = mesh.triangles_center   # (N, 3) float64
    vertices  = mesh.vertices           # (V, 3) float64

    raw_list: list[_RawMetrics] = []
    for angle, axis, label, euler_deg in _CANDIDATES:
        rot = _rotation_matrix_3x3(angle, axis)
        raw = _analyze_candidate(normals, areas, centroids, vertices, rot, label, euler_deg)
        raw_list.append(raw)

    max_height = max(r.height_mm for r in raw_list) or 1.0

    # Compute final scored candidates with height_score
    scored: list[OrientationCandidate] = [
        _finalize(r, max_height) for r in raw_list
    ]

    original = scored[0]
    best     = max(scored, key=lambda c: c.total_score)

    improvement  = best.total_score - original.total_score
    should_rotate = improvement >= 10 and best.label != "Original"
    recommended  = best if should_rotate else original

    # Support reduction percentage vs original
    support_reduction = 0.0
    if original.overhang_area_ratio > 0.001:
        support_reduction = max(0.0, (
            original.overhang_area_ratio - recommended.overhang_area_ratio
        ) / original.overhang_area_ratio * 100)

    reasons = _build_reasons(original, recommended, support_reduction, should_rotate)

    return OrientationReport(
        recommended=recommended,
        original=original,
        all_candidates=scored,
        improvement=improvement,
        should_rotate=should_rotate,
        support_reduction_pct=round(support_reduction, 1),
        reasons=reasons,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _rotation_matrix_3x3(angle: float, axis: list[float]) -> np.ndarray:
    """Rodrigues rotation matrix for angle (rad) around unit axis."""
    ax = np.array(axis, dtype=np.float64)
    ax = ax / (np.linalg.norm(ax) or 1.0)
    c, s = math.cos(angle), math.sin(angle)
    t    = 1.0 - c
    x, y, z = ax
    return np.array([
        [t*x*x + c,   t*x*y - s*z, t*x*z + s*y],
        [t*x*y + s*z, t*y*y + c,   t*y*z - s*x],
        [t*x*z - s*y, t*y*z + s*x, t*z*z + c  ],
    ], dtype=np.float64)


def _analyze_candidate(
    normals:   np.ndarray,
    areas:     np.ndarray,
    centroids: np.ndarray,
    vertices:  np.ndarray,
    rot:       np.ndarray,
    label:     str,
    euler_deg: list[float],
) -> _RawMetrics:
    """
    Compute all raw geometry metrics for one orientation.
    All operations are pure numpy — no trimesh calls, no memory allocation
    beyond the rotated arrays (which are views / O(N) temporaries).
    """
    rot_n = (rot @ normals.T).T     # (N, 3) rotated face normals
    rot_c = (rot @ centroids.T).T   # (N, 3) rotated face centroids
    rot_v = (rot @ vertices.T).T    # (V, 3) rotated vertices

    total_area = float(areas.sum())

    # ── Overhang metrics ──────────────────────────────────────────────────
    nz = rot_n[:, 2]
    overhang_mask = nz < _COS_MILD   # faces that exceed 45° from vertical

    if overhang_mask.any():
        overhang_area_ratio = float(areas[overhang_mask].sum()) / max(total_area, 1e-9)
    else:
        overhang_area_ratio = 0.0
    overhang_area_ratio = round(overhang_area_ratio, 4)

    # ── Bounding box in rotated frame ─────────────────────────────────────
    min_z = float(rot_v[:, 2].min())
    max_z = float(rot_v[:, 2].max())
    height_mm = max(max_z - min_z, 0.001)

    # ── Contact area (adapted from contact_area.py) ───────────────────────
    z_thresh = min_z + max(0.5, height_mm * 0.02)
    near_base = rot_c[:, 2] <= z_thresh
    bottom_facing = nz < -0.3   # pointing downward

    bottom_mask = near_base & bottom_facing
    if not bottom_mask.any():
        bottom_mask = near_base   # fallback: any face near base

    if bottom_mask.any():
        contact_area_mm2 = float(
            np.sum(areas[bottom_mask] * np.abs(nz[bottom_mask]))
        )
    else:
        # No base faces — rough estimate from rotated XY extents
        min_x, max_x = float(rot_v[:, 0].min()), float(rot_v[:, 0].max())
        min_y, max_y = float(rot_v[:, 1].min()), float(rot_v[:, 1].max())
        contact_area_mm2 = (max_x - min_x) * (max_y - min_y) * 0.3

    contact_area_mm2 = max(1.0, round(contact_area_mm2, 2))

    # ── Height-to-base ratio ──────────────────────────────────────────────
    hbr = round(height_mm / math.sqrt(contact_area_mm2), 4)

    # ── Sub-scores (no height_score yet — needs max_height) ──────────────
    support_score  = max(0, min(100, 100 - int(overhang_area_ratio * 300)))
    adhesion_score = _adhesion_score(contact_area_mm2)
    stability_score = _stability_score(hbr)

    return _RawMetrics(
        label=label,
        rotation_euler_deg=euler_deg,
        overhang_area_ratio=overhang_area_ratio,
        contact_area_mm2=contact_area_mm2,
        height_to_base_ratio=hbr,
        height_mm=round(height_mm, 2),
        support_score=support_score,
        adhesion_score=adhesion_score,
        stability_score=stability_score,
    )


def _adhesion_score(contact_area_mm2: float) -> int:
    if contact_area_mm2 >= 500:  return 95
    if contact_area_mm2 >= 200:  return 80
    if contact_area_mm2 >= 100:  return 65
    if contact_area_mm2 >= 50:   return 45
    return 25


def _stability_score(hbr: float) -> int:
    if hbr <= 1.5:  return 95
    if hbr <= 2.5:  return 80
    if hbr <= 3.5:  return 62
    if hbr <= 5.0:  return 42
    return 20


def _finalize(raw: _RawMetrics, max_height: float) -> OrientationCandidate:
    """Add height_score and compute weighted total."""
    height_score = max(0, min(100, 100 - int((raw.height_mm / max_height) * 80)))
    total = int(
        raw.support_score   * 0.40 +
        raw.adhesion_score  * 0.30 +
        raw.stability_score * 0.20 +
        height_score        * 0.10
    )
    return OrientationCandidate(
        label=raw.label,
        rotation_euler_deg=raw.rotation_euler_deg,
        overhang_area_ratio=raw.overhang_area_ratio,
        contact_area_mm2=raw.contact_area_mm2,
        height_to_base_ratio=raw.height_to_base_ratio,
        height_mm=raw.height_mm,
        support_score=raw.support_score,
        adhesion_score=raw.adhesion_score,
        stability_score=raw.stability_score,
        height_score=height_score,
        total_score=total,
    )


def _build_reasons(
    original:         OrientationCandidate,
    recommended:      OrientationCandidate,
    support_reduction: float,
    should_rotate:    bool,
) -> list[str]:
    if not should_rotate:
        return ["Original orientation is already optimal for this model."]

    reasons: list[str] = []

    if support_reduction > 5:
        reasons.append(
            f"Reduces overhang area from {original.overhang_area_ratio:.0%} to "
            f"{recommended.overhang_area_ratio:.0%} "
            f"({support_reduction:.0f}% less support material)."
        )

    if recommended.contact_area_mm2 > original.contact_area_mm2 * 1.2:
        reasons.append(
            f"Increases bed contact area from {original.contact_area_mm2:.0f} mm² to "
            f"{recommended.contact_area_mm2:.0f} mm² — better first-layer adhesion."
        )

    if recommended.height_mm < original.height_mm * 0.85:
        reasons.append(
            f"Reduces print height from {original.height_mm:.0f} mm to "
            f"{recommended.height_mm:.0f} mm — faster print, less tip-over risk."
        )

    if recommended.stability_score > original.stability_score + 10:
        reasons.append(
            f"Lowers height-to-base ratio from {original.height_to_base_ratio:.1f} to "
            f"{recommended.height_to_base_ratio:.1f} — more stable during printing."
        )

    if not reasons:
        reasons.append(
            f"Overall print score improves from {original.total_score} to "
            f"{recommended.total_score} points."
        )

    return reasons
