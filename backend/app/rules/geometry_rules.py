"""
AutoSlice — Geometry-driven print setting adjustments.
Uses risk scores from ModelIntent to make gradated decisions
instead of binary flags.

Every assignment goes through _set() so an optional DecisionTrace
can record exactly which rules fired and what values changed.
"""

from app.diagnostics.models import DecisionTrace
from app.models.intent import ModelIntent
from app.models.print_settings import PrintSettings


def _set(
    settings: PrintSettings,
    trace: DecisionTrace | None,
    rule: str,
    trigger: str,
    field: str,
    value,
) -> None:
    """Apply value to a settings field and record the change if tracing."""
    before = getattr(settings, field)
    setattr(settings, field, value)
    if trace is not None:
        trace.record(rule, trigger, field, before, value)


def apply_geometry_rules(
    settings: PrintSettings,
    intent: ModelIntent,
    trace: DecisionTrace | None = None,
) -> PrintSettings:
    geo = intent.raw_geometry
    bridge_span = geo.bridge.max_span_mm
    thin_mm = geo.thin_wall.min_thickness_mm

    # ------------------------------------------------------------------ #
    # SUPPORTS — type and density driven by support_risk + severity tiers
    # ------------------------------------------------------------------ #
    ov = geo.overhang

    if intent.needs_supports:
        _set(settings, trace, "geometry.supports.enabled",
             f"needs_supports=True (support_risk={intent.support_risk})",
             "supports_enabled", True)

        if intent.support_density_hint == "heavy":
            _set(settings, trace, "geometry.supports.density",
                 "support_density_hint='heavy'",
                 "support_density_percent", 25)
            _set(settings, trace, "geometry.supports.type",
                 "support_density_hint='heavy' → tree",
                 "support_type", "tree")
        elif intent.support_density_hint == "normal":
            _set(settings, trace, "geometry.supports.density",
                 "support_density_hint='normal'",
                 "support_density_percent", 15)
            # Use tree supports for severe or organic overhangs
            stype = "tree" if (ov.severe_area_ratio > 0.02 or
                               ov.overhang_area_ratio > 0.10) else "normal"
            _set(settings, trace, "geometry.supports.type",
                 f"severe_ratio={ov.severe_area_ratio:.2f}"
                 f" overhang_ratio={ov.overhang_area_ratio:.2f} → {stype}",
                 "support_type", stype)
        else:
            _set(settings, trace, "geometry.supports.density",
                 "support_density_hint='light'",
                 "support_density_percent", 10)
            _set(settings, trace, "geometry.supports.type",
                 "support_density_hint='light' → normal",
                 "support_type", "normal")

        # Tighten angle threshold for long bridges or severe overhangs
        if bridge_span > 15 or ov.severe_area_ratio > 0.02:
            _set(settings, trace, "geometry.supports.angle",
                 f"bridge_span={bridge_span:.1f}mm > 15"
                 f" or severe_overhang={ov.severe_area_ratio:.2f} → angle 40°",
                 "support_angle_threshold_deg",
                 min(settings.support_angle_threshold_deg, 40))
        elif ov.moderate_area_ratio > 0.05:
            _set(settings, trace, "geometry.supports.angle",
                 f"moderate_overhang={ov.moderate_area_ratio:.2f} > 5% → angle 45°",
                 "support_angle_threshold_deg",
                 min(settings.support_angle_threshold_deg, 45))

    # ------------------------------------------------------------------ #
    # BRIM — width driven by adhesion_risk
    # ------------------------------------------------------------------ #
    if intent.needs_brim:
        _set(settings, trace, "geometry.brim.enabled",
             f"needs_brim=True (adhesion_risk={intent.adhesion_risk})",
             "brim_enabled", True)
        if intent.adhesion_risk >= 50:
            _set(settings, trace, "geometry.brim.width",
                 f"adhesion_risk={intent.adhesion_risk} >= 50 → 8mm",
                 "brim_width_mm", 8.0)
        elif intent.adhesion_risk >= 25:
            _set(settings, trace, "geometry.brim.width",
                 f"adhesion_risk={intent.adhesion_risk} >= 25 → 5mm",
                 "brim_width_mm", 5.0)
        else:
            _set(settings, trace, "geometry.brim.width",
                 f"adhesion_risk={intent.adhesion_risk} < 25, floor 5mm",
                 "brim_width_mm", max(settings.brim_width_mm, 5.0))

    # ------------------------------------------------------------------ #
    # WALLS
    # ------------------------------------------------------------------ #
    if intent.detail_risk >= 60:
        _set(settings, trace, "geometry.walls.detail_high",
             f"detail_risk={intent.detail_risk} >= 60 → min 5 walls",
             "wall_count", max(settings.wall_count, 5))
    elif intent.detail_risk >= 30:
        _set(settings, trace, "geometry.walls.detail_medium",
             f"detail_risk={intent.detail_risk} >= 30 → min 4 walls",
             "wall_count", max(settings.wall_count, 4))
    elif intent.difficulty == "hard":
        _set(settings, trace, "geometry.walls.difficulty_hard",
             "difficulty='hard' → min 4 walls",
             "wall_count", max(settings.wall_count, 4))
    elif intent.difficulty == "moderate":
        _set(settings, trace, "geometry.walls.difficulty_moderate",
             "difficulty='moderate' → min 3 walls",
             "wall_count", max(settings.wall_count, 3))

    if intent.stability_risk >= 35:
        _set(settings, trace, "geometry.walls.stability",
             f"stability_risk={intent.stability_risk} >= 35 → min 4 walls",
             "wall_count", max(settings.wall_count, 4))

    # ------------------------------------------------------------------ #
    # INFILL — density and layers driven by difficulty
    # ------------------------------------------------------------------ #
    if intent.difficulty == "hard":
        _set(settings, trace, "geometry.infill.percent_hard",
             "difficulty='hard' → min 25%",
             "infill_percent", max(settings.infill_percent, 25))
        _set(settings, trace, "geometry.infill.top_layers_hard",
             "difficulty='hard' → min 6 top layers",
             "top_layers", max(settings.top_layers, 6))
        _set(settings, trace, "geometry.infill.bottom_layers_hard",
             "difficulty='hard' → min 5 bottom layers",
             "bottom_layers", max(settings.bottom_layers, 5))
    elif intent.difficulty == "moderate":
        _set(settings, trace, "geometry.infill.percent_moderate",
             "difficulty='moderate' → min 20%",
             "infill_percent", max(settings.infill_percent, 20))
        _set(settings, trace, "geometry.infill.top_layers_moderate",
             "difficulty='moderate' → min 5 top layers",
             "top_layers", max(settings.top_layers, 5))

    # ------------------------------------------------------------------ #
    # LAYER HEIGHT — driven by detail_risk
    # ------------------------------------------------------------------ #
    if intent.detail_risk >= 60:
        _set(settings, trace, "geometry.layer.detail_high",
             f"detail_risk={intent.detail_risk} >= 60 → max 0.12mm",
             "layer_height_mm", min(settings.layer_height_mm, 0.12))
    elif intent.detail_risk >= 30:
        _set(settings, trace, "geometry.layer.detail_medium",
             f"detail_risk={intent.detail_risk} >= 30 → max 0.15mm",
             "layer_height_mm", min(settings.layer_height_mm, 0.15))

    # ------------------------------------------------------------------ #
    # SPEED — driven by stability_risk + bridge span
    # ------------------------------------------------------------------ #
    if intent.stability_risk >= 60:
        _set(settings, trace, "geometry.speed.stability_high",
             f"stability_risk={intent.stability_risk} >= 60 → max 60mm/s",
             "print_speed_mm_s", min(settings.print_speed_mm_s, 60))
    elif intent.stability_risk >= 35:
        _set(settings, trace, "geometry.speed.stability_medium",
             f"stability_risk={intent.stability_risk} >= 35 → max 100mm/s",
             "print_speed_mm_s", min(settings.print_speed_mm_s, 100))

    if bridge_span > 3:
        _set(settings, trace, "geometry.fan.bridge",
             f"bridge_span={bridge_span:.1f}mm > 3 → min fan 80%",
             "fan_speed_percent", max(settings.fan_speed_percent, 80))
    if bridge_span > 8:
        _set(settings, trace, "geometry.fan.bridge_high",
             f"bridge_span={bridge_span:.1f}mm > 8 → max fan 100%",
             "fan_speed_percent", max(settings.fan_speed_percent, 100))
    if bridge_span > 15:
        _set(settings, trace, "geometry.speed.bridge",
             f"bridge_span={bridge_span:.1f}mm > 15 → max 80mm/s",
             "print_speed_mm_s", min(settings.print_speed_mm_s, 80))
    if bridge_span > 30:
        _set(settings, trace, "geometry.speed.bridge_long",
             f"bridge_span={bridge_span:.1f}mm > 30 → max 50mm/s (long bridge)",
             "print_speed_mm_s", min(settings.print_speed_mm_s, 50))

    # ------------------------------------------------------------------ #
    # THIN WALLS
    # ------------------------------------------------------------------ #
    if thin_mm < 999.0 and thin_mm < settings.nozzle_size_mm * 2.5:
        threshold = round(settings.nozzle_size_mm * 2.5, 3)
        _set(settings, trace, "geometry.thin_wall.walls",
             f"thin_mm={thin_mm:.2f} < nozzle*2.5={threshold} → min 4 walls",
             "wall_count", max(settings.wall_count, 4))
        _set(settings, trace, "geometry.thin_wall.layer_height",
             f"thin_mm={thin_mm:.2f} < nozzle*2.5={threshold} → max 0.15mm layer",
             "layer_height_mm", min(settings.layer_height_mm, 0.15))

    # ------------------------------------------------------------------ #
    # INFILL PATTERN
    # ------------------------------------------------------------------ #
    pattern = _select_infill_pattern(intent)
    _set(settings, trace, "geometry.infill.pattern",
         _infill_pattern_trigger(intent),
         "infill_pattern", pattern)

    # ------------------------------------------------------------------ #
    # SUPPORT INTERFACE
    # ------------------------------------------------------------------ #
    if settings.supports_enabled:
        _set(settings, trace, "geometry.support_interface.enabled",
             "supports_enabled=True → interface on",
             "support_interface_enabled", True)
        iface_layers = 3 if intent.support_risk >= 50 else 2
        _set(settings, trace, "geometry.support_interface.layers",
             f"support_risk={intent.support_risk} → {iface_layers} interface layers",
             "support_interface_layers", iface_layers)
        _set(settings, trace, "geometry.support_interface.pattern",
             "concentric for clean removal",
             "support_interface_pattern", "concentric")

    # ------------------------------------------------------------------ #
    # IRONING
    # ------------------------------------------------------------------ #
    if intent.detail_risk >= 40 and not geo.overhang.has_overhangs:
        _set(settings, trace, "geometry.ironing.flat_detail",
             f"detail_risk={intent.detail_risk} >= 40, no overhangs → iron",
             "ironing_enabled", True)
    elif intent.has_fine_detail and intent.detail_risk >= 25:
        _set(settings, trace, "geometry.ironing.fine_detail",
             f"has_fine_detail=True, detail_risk={intent.detail_risk} >= 25 → iron",
             "ironing_enabled", True)

    # ------------------------------------------------------------------ #
    # TOP SURFACE PATTERN
    # ------------------------------------------------------------------ #
    tsp = "concentric" if geo.overhang.overhang_area_ratio > 0.10 else "monotonic"
    _set(settings, trace, "geometry.top_surface.pattern",
         f"overhang_area_ratio={geo.overhang.overhang_area_ratio:.2f} → {tsp}",
         "top_surface_pattern", tsp)

    # ------------------------------------------------------------------ #
    # SEAM POSITION
    # ------------------------------------------------------------------ #
    if intent.detail_risk >= 20 or intent.has_fine_detail:
        _set(settings, trace, "geometry.seam.aligned",
             f"detail_risk={intent.detail_risk} >= 20 or has_fine_detail → aligned",
             "seam_position", "aligned")
    elif intent.difficulty == "hard" and intent.stability_risk >= 35:
        _set(settings, trace, "geometry.seam.nearest",
             f"difficulty='hard', stability_risk={intent.stability_risk} >= 35 → nearest",
             "seam_position", "nearest")
    else:
        _set(settings, trace, "geometry.seam.default",
             "default → aligned",
             "seam_position", "aligned")

    # ------------------------------------------------------------------ #
    # MINIMUM LAYER TIME
    # ------------------------------------------------------------------ #
    if intent.detail_risk >= 50:
        _set(settings, trace, "geometry.min_layer_time.high",
             f"detail_risk={intent.detail_risk} >= 50 → min 15s",
             "min_layer_time_s", max(settings.min_layer_time_s, 15))
    elif intent.detail_risk >= 30:
        _set(settings, trace, "geometry.min_layer_time.medium",
             f"detail_risk={intent.detail_risk} >= 30 → min 12s",
             "min_layer_time_s", max(settings.min_layer_time_s, 12))

    # ------------------------------------------------------------------ #
    # SUPPORT GAPS
    # ------------------------------------------------------------------ #
    if settings.supports_enabled:
        if intent.support_risk >= 60:
            _set(settings, trace, "geometry.support_gap.tight",
                 f"support_risk={intent.support_risk} >= 60 → 0.2mm Z gap",
                 "support_top_z_distance_mm",
                 min(settings.support_top_z_distance_mm, 0.2))
        elif intent.support_risk <= 20:
            _set(settings, trace, "geometry.support_gap.relaxed",
                 f"support_risk={intent.support_risk} <= 20 → 0.25mm Z gap",
                 "support_top_z_distance_mm",
                 max(settings.support_top_z_distance_mm, 0.25))

    return settings


# ── Helpers ──────────────────────────────────────────────────────────────────

def _infill_pattern_trigger(intent: ModelIntent) -> str:
    geo = intent.raw_geometry
    if intent.stability_risk >= 50 or intent.is_structurally_risky:
        return f"stability_risk={intent.stability_risk} >= 50 or is_structurally_risky → cubic"
    if intent.detail_risk >= 30 and geo.overhang.overhang_area_ratio > 0.05:
        return (f"detail_risk={intent.detail_risk} >= 30, "
                f"overhang_ratio={geo.overhang.overhang_area_ratio:.2f} > 0.05 → gyroid")
    if geo.thin_wall.has_thin_walls and intent.detail_risk >= 15:
        return f"has_thin_walls=True, detail_risk={intent.detail_risk} >= 15 → gyroid"
    return f"stability_risk={intent.stability_risk}, difficulty={intent.difficulty!r} → grid"


def _select_infill_pattern(intent: ModelIntent) -> str:
    geo = intent.raw_geometry
    if intent.stability_risk >= 50 or intent.is_structurally_risky:
        return "cubic"
    if intent.detail_risk >= 30 and geo.overhang.overhang_area_ratio > 0.05:
        return "gyroid"
    if geo.thin_wall.has_thin_walls and intent.detail_risk >= 15:
        return "gyroid"
    if intent.stability_risk >= 25 or intent.difficulty == "moderate":
        return "grid"
    return "grid"
