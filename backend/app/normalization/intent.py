"""
AutoSlice — Normalization layer.
Converts GeometryAnalysis into a slicer-agnostic ModelIntent.
"""

from app.models.geometry import GeometryAnalysis
from app.models.intent import ModelIntent

# Thresholds
_LARGE_MODEL_MM = 150.0
_SMALL_MODEL_MM = 50.0
_HARD_OVERHANG_RATIO = 0.15
_BRIDGE_BRIM_TRIGGER_MM = 20.0
_STRUCTURALLY_RISKY_ASPECT_RATIO = 4.0   # height > 4x the narrower base dimension


def normalize(analysis: GeometryAnalysis) -> ModelIntent:
    """
    Apply threshold-based rules to convert raw geometry data into
    a high-level ModelIntent that the Rules Engine consumes.
    """
    bb = analysis.bounding_box

    # --- Size class ---
    max_dim = max(bb.x_mm, bb.y_mm, bb.z_mm)
    if max_dim >= _LARGE_MODEL_MM:
        size_class = "large"
    elif max_dim >= _SMALL_MODEL_MM:
        size_class = "medium"
    else:
        size_class = "small"

    # --- Support need ---
    needs_supports = analysis.overhang.has_overhangs

    # --- Support density hint ---
    if analysis.overhang.overhang_area_ratio > _HARD_OVERHANG_RATIO:
        support_density_hint = "heavy"
    elif needs_supports:
        support_density_hint = "normal"
    else:
        support_density_hint = "light"

    # --- Brim ---
    needs_brim = (
        size_class == "large" or
        analysis.bridge.max_span_mm > _BRIDGE_BRIM_TRIGGER_MM or
        analysis.thin_wall.has_thin_walls
    )

    # --- Fine detail ---
    has_fine_detail = analysis.thin_wall.has_thin_walls

    # --- Structural risk: tall and thin (aspect ratio check) ---
    base_min = min(bb.x_mm, bb.y_mm)
    is_structurally_risky = (
        base_min > 0 and
        (bb.z_mm / base_min) > _STRUCTURALLY_RISKY_ASPECT_RATIO and
        not needs_supports
    )

    # --- Difficulty ---
    if analysis.overhang.overhang_area_ratio > _HARD_OVERHANG_RATIO or is_structurally_risky:
        difficulty = "hard"
    elif needs_supports or analysis.bridge.has_bridges:
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
    )
