"""
AutoSlice — AI orientation suggestion engine.

suggest(request) → OrientationSuggestion

Pure functions. No side effects. No I/O. No mesh required.
Works from bounding-box dimensions and scalar geometry features only.

NOTE: Overhang estimates for non-original orientations are heuristic
approximations derived from base-area geometry, not mesh face analysis.
For precision, use the mesh-based scorer via GET /api/analyze/{job_id}
which returns an orientation field with exact overhang data.

Algorithm:
  1. Enumerate 7 candidate rotations covering all meaningful 90°/180° increments:
       [0,0,0]   Original
       [90,0,0]  Lay on depth axis  (new base: W×H)
       [0,90,0]  Lay on width axis  (new base: H×D)
       [0,0,90]  Spin Z 90°         (new base: D×W — same area as Original)
       [180,0,0] Flip upside-down X (same base, ~50% overhang reduction)
       [0,180,0] Flip upside-down Y (same base, ~45% overhang reduction)
       [0,0,180] Spin Z 180°        (same base, overhang unchanged)
  2. For each: compute base_area, print_height, HBR, and estimated overhang.
  3. Score: support 40% + adhesion 30% + stability 20% + height 10%
     (identical weights to app/orientation/scorer.py for consistency).
  4. Recommend if the best orientation beats Original by ≥ 10 points.
  5. Ties broken by list order — Original beats Z-spin equivalents;
     X+180° beats Y+180° (slightly higher overhang reduction).
  6. Return OrientationHints with orientation_euler_deg for the Apply bridge.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.ai.schemas import (
    OrientationHints,
    OrientationRequest,
    OrientationSuggestion,
    Rotation3D,
)


# ─────────────────────────────────────────────────────────────────────────────
# Candidate orientation definitions
#
# Each config maps bounding-box dimensions (W, D, H) through index triplets:
#   b1, b2      → the two dimensions that form the base (XY footprint)
#   hi          → the dimension that becomes the print height (Z)
#   flip_factor → fraction of original overhang that remains after this rotation
#                 (0.0 = not a flip; use area-based estimation instead)
#
# Tie-breaking is deterministic: max() is stable — first max wins.
# Candidates with the same bounding-box footprint as Original (Z+90°, Z+180°)
# produce identical scores, so Original is preferred.  X+180° has a lower
# flip_factor than Y+180° (more overhang removed) so X+180° wins that tie.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _Config:
    label:       str
    rotation:    tuple[float, float, float]  # (rx, ry, rz) in degrees
    b1:          int                         # base dim 1 index into (W, D, H)
    b2:          int                         # base dim 2 index into (W, D, H)
    hi:          int                         # height dim index into (W, D, H)
    flip_factor: float = 0.0                 # >0: fraction of overhang remaining; 0 = not a flip


_CONFIGS: list[_Config] = [
    _Config("Original",  (  0,   0,   0), b1=0, b2=1, hi=2),
    _Config("X+90°",     ( 90,   0,   0), b1=0, b2=2, hi=1),
    _Config("Y+90°",     (  0,  90,   0), b1=2, b2=1, hi=0),
    _Config("Z+90°",     (  0,   0,  90), b1=1, b2=0, hi=2),
    _Config("X+180°",    (180,   0,   0), b1=0, b2=1, hi=2, flip_factor=0.50),
    _Config("Y+180°",    (  0, 180,   0), b1=0, b2=1, hi=2, flip_factor=0.55),
    _Config("Z+180°",    (  0,   0, 180), b1=0, b2=1, hi=2),
]


@dataclass
class _Candidate:
    label:              str
    rotation:           tuple[float, float, float]
    base_area:          float
    height_mm:          float
    hbr:                float
    overhang_estimate:  float
    support_score:      int
    adhesion_score:     int
    stability_score:    int
    height_score:       int = 0
    total_score:        int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Sub-scores — identical thresholds to app/orientation/scorer.py
# ─────────────────────────────────────────────────────────────────────────────

def _adhesion_score(contact_area_mm2: float) -> int:
    if contact_area_mm2 >= 500: return 95
    if contact_area_mm2 >= 200: return 80
    if contact_area_mm2 >= 100: return 65
    if contact_area_mm2 >=  50: return 45
    return 25


def _stability_score(hbr: float) -> int:
    if hbr <= 1.5: return 95
    if hbr <= 2.5: return 80
    if hbr <= 3.5: return 62
    if hbr <= 5.0: return 42
    return 20


def _support_score(overhang_estimate: float) -> int:
    return max(0, min(100, 100 - int(overhang_estimate * 300)))


# ─────────────────────────────────────────────────────────────────────────────
# Overhang estimation per orientation
#
# The provided overhang_ratio is measured in the original orientation.
# When rotating, we approximate how it changes:
#   - Flip: upside-down often halves overhang (top features become bed-supported)
#   - Side: reduction proportional to the base-area gain vs original
# ─────────────────────────────────────────────────────────────────────────────

def _estimate_overhang(
    cfg:                  _Config,
    original_overhang:    float,
    original_base_area:   float,
    candidate_base_area:  float,
) -> float:
    # Flip rotations (X+180°, Y+180°): top face lands on the bed.
    # flip_factor is the fraction of original overhang that remains.
    if cfg.flip_factor > 0.0:
        return original_overhang * cfg.flip_factor

    # Non-flip rotations: larger base area → more geometry supported from below.
    # Z+90° and Z+180° have the same base area as Original, so no improvement.
    if candidate_base_area <= original_base_area * 1.05:
        return original_overhang

    area_gain  = (candidate_base_area / original_base_area) - 1.0
    reduction  = min(0.65, area_gain * 0.50)
    return max(0.0, original_overhang * (1.0 - reduction))


# ─────────────────────────────────────────────────────────────────────────────
# Confidence
# ─────────────────────────────────────────────────────────────────────────────

def _confidence(
    gap:            int,
    overhang_ratio: float,
    dims:           tuple[float, float, float],
) -> int:
    """
    Score gap drives the base; penalties for symmetric models (where rotation
    matters less) and for high overhang (where scalar estimate is less reliable).
    """
    if   gap >= 30: base = 85
    elif gap >= 15: base = 68
    elif gap >=  5: base = 45
    else:           base = 20

    # Elongated models → recommendation is more reliable
    d_sorted   = sorted(dims)
    elongation = d_sorted[2] / max(d_sorted[0], 1.0)
    symmetry_penalty = max(0, 30 - int(elongation * 8))

    overhang_penalty = int(overhang_ratio * 25)

    return max(10, min(95, base - symmetry_penalty - overhang_penalty))


# ─────────────────────────────────────────────────────────────────────────────
# Explanation and warnings
# ─────────────────────────────────────────────────────────────────────────────

def _build_explanation(
    original:          _Candidate,
    recommended:       _Candidate,
    support_reduction: float,
    should_rotate:     bool,
) -> str:
    if not should_rotate:
        delta = recommended.total_score - original.total_score
        return (
            "The original orientation already scores highest. "
            f"No rotation improves the combined score by 10+ points "
            f"(best alternative: {recommended.label}, "
            f"Δ{delta:+d} pt{'s' if abs(delta) != 1 else ''})."
        )

    parts = [f"Rotating to {recommended.label} is recommended."]
    if support_reduction >= 5:
        parts.append(f"Estimated support material reduces by ~{support_reduction:.0f}%.")
    if recommended.adhesion_score > original.adhesion_score + 10:
        parts.append(
            f"Bed contact area increases from ~{original.base_area:.0f} mm² "
            f"to ~{recommended.base_area:.0f} mm²."
        )
    if recommended.height_mm < original.height_mm * 0.90:
        parts.append(
            f"Print height drops from {original.height_mm:.0f} mm "
            f"to {recommended.height_mm:.0f} mm."
        )
    if recommended.stability_score > original.stability_score + 10:
        parts.append(
            f"Height-to-base ratio improves from {original.hbr:.1f} "
            f"to {recommended.hbr:.1f}."
        )
    return " ".join(parts)


def _build_warnings(
    overhang_ratio:  float,
    thin_wall_ratio: float,
    gap:             int,
    should_rotate:   bool,
) -> list[str]:
    warnings: list[str] = [
        "Orientation estimates use bounding-box heuristics. "
        "Run the full mesh analyzer for exact overhang data."
    ]

    if not should_rotate:
        warnings.append(
            "Original orientation already scores highest — no rotation is needed."
        )
        return warnings

    if overhang_ratio > 0.50:
        warnings.append(
            f"Overhang ratio {overhang_ratio:.0%} is high. "
            "Scalar estimate is approximate; mesh-based analysis is recommended."
        )

    if thin_wall_ratio > 0.20:
        warnings.append(
            "Thin walls detected. Preferred orientation keeps thin features "
            "perpendicular to the build plate for best layer adhesion."
        )

    if gap < 10:
        warnings.append(
            "Score difference is small — the model has similar printability "
            "across orientations. Either choice is acceptable."
        )

    return warnings


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def suggest(request: OrientationRequest) -> OrientationSuggestion:
    """Analyse scalar bounding-box geometry and return the best 90° rotation."""
    dims              = (request.width_mm, request.depth_mm, request.height_mm)
    original_base_area = dims[0] * dims[1]

    candidates: list[_Candidate] = []
    for cfg in _CONFIGS:
        base_area = dims[cfg.b1] * dims[cfg.b2]
        height_mm = dims[cfg.hi]
        hbr       = height_mm / math.sqrt(max(base_area, 1.0))
        overhang  = _estimate_overhang(
            cfg, request.overhang_ratio, original_base_area, base_area
        )
        candidates.append(_Candidate(
            label             = cfg.label,
            rotation          = cfg.rotation,
            base_area         = round(base_area, 2),
            height_mm         = round(height_mm, 2),
            hbr               = round(hbr, 3),
            overhang_estimate = round(overhang, 4),
            support_score     = _support_score(overhang),
            adhesion_score    = _adhesion_score(base_area),
            stability_score   = _stability_score(hbr),
        ))

    max_height = max(c.height_mm for c in candidates) or 1.0
    for c in candidates:
        c.height_score = max(0, min(100, 100 - int((c.height_mm / max_height) * 80)))
        c.total_score  = int(
            c.support_score   * 0.40 +
            c.adhesion_score  * 0.30 +
            c.stability_score * 0.20 +
            c.height_score    * 0.10
        )

    original      = candidates[0]
    best          = max(candidates, key=lambda c: c.total_score)
    gap           = best.total_score - original.total_score
    should_rotate = gap >= 10 and best.label != "Original"
    recommended   = best if should_rotate else original

    if original.overhang_estimate > 0.001:
        support_reduction = max(0.0, (
            original.overhang_estimate - recommended.overhang_estimate
        ) / original.overhang_estimate * 100.0)
    else:
        support_reduction = 0.0

    rx, ry, rz = recommended.rotation

    return OrientationSuggestion(
        recommended_rotation = Rotation3D(x=rx, y=ry, z=rz),
        confidence           = _confidence(gap, request.overhang_ratio, dims),
        estimated_support_reduction_percent = round(support_reduction, 1),
        bed_adhesion_score   = recommended.adhesion_score,
        stability_score      = recommended.stability_score,
        warnings             = _build_warnings(
            request.overhang_ratio, request.thin_wall_ratio, gap, should_rotate
        ),
        explanation          = _build_explanation(
            original, recommended, support_reduction, should_rotate
        ),
        orientation_hints    = OrientationHints(
            orientation_euler_deg=[float(rx), float(ry), float(rz)]
        ),
    )
