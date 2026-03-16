"""
AutoSlice — Normalization layer.
Converts GeometryAnalysis into a slicer-agnostic ModelIntent with risk scores.

Risk scores (0–100):
  support_risk  — probability that unsupported areas will fail
  adhesion_risk — probability of bed detachment / warping
  stability_risk — probability of shift or collapse mid-print
  detail_risk    — probability that fine features will be lost

Improvements over v1:
  - support_risk uses 3-tier overhang severity zones (mild/moderate/severe).
  - stability_risk factors in slenderness_ratio and center_of_mass_z_ratio.
  - adhesion_risk uses slenderness_ratio as an additional signal.
  - Bridge risk is considered in support density hint.
"""

from app.models.geometry import GeometryAnalysis
from app.models.intent import ModelIntent


# --- Thresholds ---
_LARGE_MODEL_MM         = 150.0
_SMALL_MODEL_MM         = 50.0
_SUPPORT_AREA_THRESHOLD = 0.02   # 2% moderate/severe overhang triggers supports
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
    slenderness = analysis.slenderness_ratio
    com_z = analysis.center_of_mass_z_ratio

    # Size class
    max_dim = max(bb.x_mm, bb.y_mm, bb.z_mm)
    size_class = (
        "large" if max_dim >= _LARGE_MODEL_MM else
        ("medium" if max_dim >= _SMALL_MODEL_MM else "small")
    )

    # --- support_risk ---
    # Uses 3-tier overhang severity zones for more granular scoring
    support_risk = 0

    # Mild overhangs (45-55 deg) - low risk on their own
    if overhang.mild_area_ratio > 0.10:
        support_risk += 10

    # Moderate overhangs (55-65 deg) - likely need support
    if overhang.moderate_area_ratio > 0.02:
        support_risk += 20
    if overhang.moderate_area_ratio > 0.08:
        support_risk += 10

    # Severe overhangs (65 deg+) - always need support
    if overhang.severe_area_ratio > 0.005:
        support_risk += 25
    if overhang.severe_area_ratio > 0.05:
        support_risk += 15

    # Worst-case angle
    if overhang.max_angle_deg > 70:
        support_risk += 10

    # Bridge contribution to support risk
    if bridge.max_span_mm > 10:
        support_risk += 10
    if bridge.max_span_mm > 20:
        support_risk += 10

    support_risk = min(100, support_risk)

    # --- adhesion_risk ---
    adhesion_risk = 0
    if contact > 0:
        if contact < 50:
            adhesion_risk += 50
        elif contact < 100:
            adhesion_risk += 35
        elif contact < 300:
            adhesion_risk += 15
    if hbr > _BRIM_HBR_THRESHOLD:
        adhesion_risk += 15
    if hbr > 4.0:
        adhesion_risk += 15
    # Slenderness amplifies adhesion risk for narrow tall models
    if slenderness > 4.0:
        adhesion_risk += 10
    if max(bb.x_mm, bb.y_mm) > 150:
        adhesion_risk += 10
    adhesion_risk = min(100, adhesion_risk)

    # --- stability_risk ---
    stability_risk = 0
    if hbr > 0:
        if hbr > _RISKY_HBR:
            stability_risk += 30
        if hbr > 5.0:
            stability_risk += 20
        if hbr > 7.0:
            stability_risk += 20
    else:
        base_min = min(bb.x_mm, bb.y_mm)
        if base_min > 0 and (bb.z_mm / base_min) > _RISKY_ASPECT_RATIO:
            stability_risk += 40

    # Slenderness + HBR compound risk
    if slenderness > 3.0 and hbr > 2.0:
        stability_risk += 10

    # Top-heavy center of mass
    if com_z > 0.65:
        stability_risk += 15
    elif com_z > 0.55:
        stability_risk += 5

    stability_risk = min(100, stability_risk)

    # --- detail_risk ---
    detail_risk = 0
    if thin_wall.has_thin_walls:
        detail_risk += 35
    if thin_wall.min_thickness_mm < 0.8:
        detail_risk += 35
    elif thin_wall.min_thickness_mm < 1.2:
        detail_risk += 25
    elif thin_wall.min_thickness_mm < 2.0:
        detail_risk += 10
    if 0 < bb.z_mm < 3.0:
        detail_risk += 20
    detail_risk = min(100, detail_risk)

    # --- Decisions ---
    needs_supports = (
        overhang.moderate_area_ratio > _SUPPORT_AREA_THRESHOLD or
        overhang.severe_area_ratio   > 0.005 or
        overhang.max_angle_deg       > _SUPPORT_ANGLE_HARD or
        support_risk                 >= 35
    )

    if support_risk >= 70 or overhang.severe_area_ratio > 0.05:
        support_density_hint = "heavy"
    elif support_risk >= 35 or overhang.moderate_area_ratio > 0.05:
        support_density_hint = "normal"
    else:
        support_density_hint = "light"

    needs_brim = (
        adhesion_risk >= 25 or
        (contact > 0 and contact < _BRIM_CONTACT_THRESHOLD) or
        hbr > _BRIM_HBR_THRESHOLD or
        slenderness > 4.0 or
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
