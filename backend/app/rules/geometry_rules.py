"""
AutoSlice — Geometry-driven print setting adjustments.
Uses risk scores from ModelIntent to make gradated decisions
instead of binary flags.
"""

from app.models.intent import ModelIntent
from app.models.print_settings import PrintSettings


def apply_geometry_rules(settings: PrintSettings, intent: ModelIntent) -> PrintSettings:
    geo = intent.raw_geometry
    bridge_span = geo.bridge.max_span_mm
    thin_mm = geo.thin_wall.min_thickness_mm

    # ------------------------------------------------------------------ #
    # SUPPORTS — type and density driven by support_risk
    # ------------------------------------------------------------------ #
    if intent.needs_supports:
        settings.supports_enabled = True
        if intent.support_density_hint == "heavy":
            settings.support_density_percent = 25
            settings.support_type = "tree"
        elif intent.support_density_hint == "normal":
            settings.support_density_percent = 15
            settings.support_type = (
                "tree" if geo.overhang.overhang_area_ratio > 0.10 else "normal"
            )
        else:
            settings.support_density_percent = 10
            settings.support_type = "normal"

        if bridge_span > 15:
            settings.support_angle_threshold_deg = min(settings.support_angle_threshold_deg, 40)

    # ------------------------------------------------------------------ #
    # BRIM — width driven by adhesion_risk
    # ------------------------------------------------------------------ #
    if intent.needs_brim:
        settings.brim_enabled = True
        if intent.adhesion_risk >= 50:
            settings.brim_width_mm = 8.0
        elif intent.adhesion_risk >= 25:
            settings.brim_width_mm = 5.0
        else:
            settings.brim_width_mm = max(settings.brim_width_mm, 5.0)

    # ------------------------------------------------------------------ #
    # WALLS
    # ------------------------------------------------------------------ #
    if intent.detail_risk >= 60:
        settings.wall_count = max(settings.wall_count, 5)
    elif intent.detail_risk >= 30:
        settings.wall_count = max(settings.wall_count, 4)
    elif intent.difficulty == "hard":
        settings.wall_count = max(settings.wall_count, 4)
    elif intent.difficulty == "moderate":
        settings.wall_count = max(settings.wall_count, 3)

    if intent.stability_risk >= 35:
        settings.wall_count = max(settings.wall_count, 4)

    # ------------------------------------------------------------------ #
    # INFILL
    # ------------------------------------------------------------------ #
    if intent.difficulty == "hard":
        settings.infill_percent = max(settings.infill_percent, 25)
        settings.top_layers = max(settings.top_layers, 6)
        settings.bottom_layers = max(settings.bottom_layers, 5)
    elif intent.difficulty == "moderate":
        settings.infill_percent = max(settings.infill_percent, 20)
        settings.top_layers = max(settings.top_layers, 5)

    # ------------------------------------------------------------------ #
    # LAYER HEIGHT — driven by detail_risk
    # ------------------------------------------------------------------ #
    if intent.detail_risk >= 60:
        settings.layer_height_mm = min(settings.layer_height_mm, 0.12)
    elif intent.detail_risk >= 30:
        settings.layer_height_mm = min(settings.layer_height_mm, 0.15)

    # ------------------------------------------------------------------ #
    # SPEED — driven by stability_risk + bridge span
    # ------------------------------------------------------------------ #
    if intent.stability_risk >= 60:
        settings.print_speed_mm_s = min(settings.print_speed_mm_s, 60)
    elif intent.stability_risk >= 35:
        settings.print_speed_mm_s = min(settings.print_speed_mm_s, 100)

    if bridge_span > 5:
        settings.fan_speed_percent = max(settings.fan_speed_percent, 80)
    if bridge_span > 15:
        settings.print_speed_mm_s = min(settings.print_speed_mm_s, 80)

    # ------------------------------------------------------------------ #
    # THIN WALLS
    # ------------------------------------------------------------------ #
    if thin_mm < 999.0 and thin_mm < settings.nozzle_size_mm * 2.5:
        settings.wall_count = max(settings.wall_count, 4)
        settings.layer_height_mm = min(settings.layer_height_mm, 0.15)

    # ------------------------------------------------------------------ #
    # INFILL PATTERN
    # Priority: structural > organic/detail > default
    # ------------------------------------------------------------------ #
    settings.infill_pattern = _select_infill_pattern(intent)

    # ------------------------------------------------------------------ #
    # SUPPORT INTERFACE — improves detachability and under-surface quality
    # Enable whenever supports are on; use more layers for higher support_risk
    # ------------------------------------------------------------------ #
    if settings.supports_enabled:
        settings.support_interface_enabled = True
        settings.support_interface_layers = 3 if intent.support_risk >= 50 else 2
        settings.support_interface_pattern = "concentric"

    # ------------------------------------------------------------------ #
    # IRONING — re-traces flat top layers for mirror-smooth finish
    # Only worthwhile for high-detail models without heavy overhangs
    # (overhang-heavy models rarely have flat tops worth ironing)
    # ------------------------------------------------------------------ #
    if intent.detail_risk >= 40 and not geo.overhang.has_overhangs:
        settings.ironing_enabled = True
    elif intent.has_fine_detail and intent.detail_risk >= 25:
        settings.ironing_enabled = True

    # ------------------------------------------------------------------ #
    # TOP SURFACE PATTERN
    # Monotonic is always better than default lines (no visible seams)
    # Concentric for organic/round models
    # ------------------------------------------------------------------ #
    if geo.overhang.overhang_area_ratio > 0.10:
        settings.top_surface_pattern = "concentric"
    else:
        settings.top_surface_pattern = "monotonic"

    # ------------------------------------------------------------------ #
    # SEAM POSITION
    # Aligned: seam hidden at back — best for visual models
    # Nearest: minimal travel — best for structural/speed
    # ------------------------------------------------------------------ #
    if intent.detail_risk >= 20 or intent.has_fine_detail:
        settings.seam_position = "aligned"
    elif intent.difficulty == "hard" and intent.stability_risk >= 35:
        settings.seam_position = "nearest"
    else:
        settings.seam_position = "aligned"

    return settings


def _select_infill_pattern(intent: ModelIntent) -> str:
    geo = intent.raw_geometry

    # Structural / load-bearing → cubic (strongest in all 3 axes)
    if intent.stability_risk >= 50 or intent.is_structurally_risky:
        return "cubic"

    # Organic / fine detail with overhangs → gyroid (isotropic, smooth finish)
    if intent.detail_risk >= 30 and geo.overhang.overhang_area_ratio > 0.05:
        return "gyroid"

    # Thin-walled models → gyroid (distributes stress evenly, reduces print artifacts)
    if geo.thin_wall.has_thin_walls and intent.detail_risk >= 15:
        return "gyroid"

    # Moderate structural concern → grid (predictable strength, fast)
    if intent.stability_risk >= 25 or intent.difficulty == "moderate":
        return "grid"

    return "grid"
