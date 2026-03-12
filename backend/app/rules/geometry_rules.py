"""
AutoSlice — Geometry-driven print setting adjustments.
"""

from app.models.intent import ModelIntent
from app.models.print_settings import PrintSettings


def apply_geometry_rules(settings: PrintSettings, intent: ModelIntent) -> PrintSettings:
    # --- Supports ---
    if intent.needs_supports:
        settings.supports_enabled = True
        if intent.support_density_hint == "heavy":
            settings.support_density_percent = 25
            settings.support_type = "tree"
        elif intent.support_density_hint == "normal":
            settings.support_density_percent = 15
            settings.support_type = "normal"
        else:
            settings.support_density_percent = 10
            settings.support_type = "normal"

    # --- Difficulty ---
    if intent.difficulty == "hard":
        settings.wall_count = max(settings.wall_count, 4)
        settings.infill_percent = max(settings.infill_percent, 25)
        settings.top_layers = max(settings.top_layers, 6)
        settings.bottom_layers = max(settings.bottom_layers, 5)
    elif intent.difficulty == "moderate":
        settings.wall_count = max(settings.wall_count, 3)
        settings.infill_percent = max(settings.infill_percent, 20)

    # --- Bridge: maximize fan cooling ---
    if intent.raw_geometry.bridge.has_bridges and intent.raw_geometry.bridge.max_span_mm > 10:
        settings.fan_speed_percent = max(settings.fan_speed_percent, 80)

    # --- Fine detail: finer layers + more walls ---
    if intent.has_fine_detail:
        settings.layer_height_mm = min(settings.layer_height_mm, 0.15)
        settings.wall_count = max(settings.wall_count, 4)

    # --- Brim ---
    if intent.needs_brim:
        settings.brim_enabled = True
        settings.brim_width_mm = max(settings.brim_width_mm, 8.0)

    # --- Structural risk: slow down, reinforce ---
    if intent.is_structurally_risky:
        settings.print_speed_mm_s = min(settings.print_speed_mm_s, 80)
        settings.wall_count = max(settings.wall_count, 5)
        settings.infill_percent = max(settings.infill_percent, 20)

    return settings
