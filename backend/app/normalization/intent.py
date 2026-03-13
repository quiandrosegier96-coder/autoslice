"""
AutoSlice — Normalization layer.
Converts GeometryAnalysis into a slicer-agnostic ModelIntent with risk scores.

Risk scores (0–100):
  support_risk  — probability that unsupported areas will fail
  adhesion_risk — probability of bed detachment / warping
  stability_risk — probability of shift or collapse mid-print
  detail_risk    — probability that fine features will be lost
"""

from app.models.geometry import GeometryAnalysis
from app.models.intent import ModelIntent


# --- Thresholds ---
_LARGE_MODEL_MM         = 150.0
_SMALL_MODEL_MM         = 50.0
_SUPPORT_AREA_THRESHOLD = 0.04   # 4% of surface area overhanging triggers supports
_SUPPORT_ANGLE_HARD     = 55.0   # extreme angle always triggers supports
_BRIM_HBR_THRESHOLD     = 2.5
_BRIM_CONTACT_THRESHOLD = 200.0  # mm²
_RISKY_HBR              = 3.5
_RISKY_ASPECT_RATIO     = 4.0    # fallback when HBR not available


def normalize(analysis: GeometryAnalysis) -> ModelIntent:
    bb = analysis.bounding_box
    overhang = analysis.overhang
    bridge = analysis.bridge
    thin_wall = analysis.thin_wall
    hbr = analysis.height_to_base_ratio
    contact = analysis.contact_area_mm2

    # Size class
    max_dim = max(bb.x_mm, bb.y_mm, bb.z_mm)
    size_class = "large" if max_dim >= _LARGE_MODEL_MM else ("medium" if max_dim >= _SMALL_MODEL_MM else "small")

    # --- support_risk ---
    support_risk = 0
    if overhang.max_angle_deg > 45:
        support_risk += 25
    if overhang.max_angle_deg > 60:
        support_risk += 20
    if overhang.overhang_area_ratio > 0.05:
        support_risk += 20
    if overhang.overhang_area_ratio > 0.15:
        support_risk += 15
    if bridge.max_span_mm > 10:
        support_risk += 10
    if bridge.max_span_mm > 20:
        support_risk += 10
    support_risk = min(100, support_risk)

    # --- adhesion_risk ---
    adhesion_risk = 0
    if contact > 0:
        if contact < 100:
            adhesion_risk += 40
        elif contact < 300:
            adhesion_risk += 20
    if hbr > _BRIM_HBR_THRESHOLD:
        adhesion_risk += 20
    if hbr > 4.0:
        adhesion_risk += 15
    if max(bb.x_mm, bb.y_mm) > 150:
        adhesion_risk += 10
    adhesion_risk = min(100, adhesion_risk)

    # --- stability_risk ---
    stability_risk = 0
    if hbr > 0:
        if hbr > _RISKY_HBR:
            stability_risk += 35
        if hbr > 5.0:
            stability_risk += 25
        if hbr > 7.0:
            stability_risk += 20
    else:
        base_min = min(bb.x_mm, bb.y_mm)
        if base_min > 0 and (bb.z_mm / base_min) > _RISKY_ASPECT_RATIO:
            stability_risk += 40
    stability_risk = min(100, stability_risk)

    # --- detail_risk ---
    detail_risk = 0
    if thin_wall.has_thin_walls:
        detail_risk += 40
    if thin_wall.min_thickness_mm < 1.2:
        detail_risk += 30
    elif thin_wall.min_thickness_mm < 2.0:
        detail_risk += 15
    if 0 < bb.z_mm < 3.0:
        detail_risk += 20
    detail_risk = min(100, detail_risk)

    # --- Decisions ---
    needs_supports = (
        overhang.overhang_area_ratio > _SUPPORT_AREA_THRESHOLD or
        overhang.max_angle_deg > _SUPPORT_ANGLE_HARD or
        support_risk >= 35
    )

    if support_risk >= 70:
        support_density_hint = "heavy"
    elif support_risk >= 35:
        support_density_hint = "normal"
    else:
        support_density_hint = "light"

    needs_brim = (
        adhesion_risk >= 25 or
        (contact > 0 and contact < _BRIM_CONTACT_THRESHOLD) or
        hbr > _BRIM_HBR_THRESHOLD or
        (size_class == "large" and max(bb.x_mm, bb.y_mm) > 150)
    )

    has_fine_detail = detail_risk >= 30
    is_structurally_risky = stability_risk >= 35

    if support_risk >= 60 or stability_risk >= 60 or detail_risk >= 60:
        difficulty = "hard"
    elif needs_supports or bridge.has_bridges or is_structurally_risky or detail_risk >= 30:
        difficulty = "moderate"
    else:
        difficulty = "easy"

    return ModelIntent(
        difficulty=difficulty,
        needs_supports=needs_supports,
        support_density_hint=support_density_hint,
        needs_brim=needs_brim,
        size_class=size_class,
        has_fine_detail=has_fine_detail,
        is_structurally_risky=is_structurally_risky,
        raw_geometry=analysis,
        support_risk=support_risk,
        adhesion_risk=adhesion_risk,
        stability_risk=stability_risk,
        detail_risk=detail_risk,
    )
