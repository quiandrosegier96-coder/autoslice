"""
AutoSlice — Nozzle-size specific profile adjustments.

Each nozzle size has different optimal settings:
- 0.2mm: very fine detail, slow, thin layers, higher temp
- 0.4mm: standard (no override, base profile is designed for this)
- 0.6mm: fast, thick layers, lower temp needed less
"""

from app.models.print_settings import PrintSettings


# Optimal settings per nozzle diameter
_NOZZLE_PROFILES: dict[float, dict] = {
    0.2: {
        "layer_height_mm":         0.1,    # max ~75% of 0.2mm nozzle
        "first_layer_height_mm":   0.2,    # full nozzle diameter for adhesion
        "print_speed_mm_s":        80,     # low volumetric flow limit
        "first_layer_speed_mm_s":  20,     # very slow first layer for adhesion
        "wall_count":              4,      # more walls for strength (thin walls)
        "top_layers":              7,      # more top layers (thinner = more needed)
        "bottom_layers":           5,
        "nozzle_temp_offset_c":    5,      # slightly hotter for small melt zone
        "fan_speed_percent":       100,
        "fan_first_layer":         False,
    },
    0.4: {
        # Standard — no overrides, base profile handles this
    },
    0.6: {
        "layer_height_mm":         0.35,
        "first_layer_height_mm":   0.4,
        "print_speed_mm_s":        250,    # higher volumetric capacity
        "first_layer_speed_mm_s":  40,
        "wall_count":              3,
        "top_layers":              4,
        "bottom_layers":           3,
        "nozzle_temp_offset_c":    0,
        "fan_speed_percent":       80,
        "fan_first_layer":         False,
    },
}


def apply_nozzle_profile(settings: PrintSettings, nozzle_size_mm: float) -> PrintSettings:
    """
    Apply nozzle-specific overrides after the rules engine.
    Only overrides values that are truly nozzle-dependent.
    """
    # Find closest profile key
    closest = min(_NOZZLE_PROFILES.keys(), key=lambda k: abs(k - nozzle_size_mm))
    # Only apply if within 0.05mm tolerance (so 0.2 matches 0.2, etc.)
    if abs(closest - nozzle_size_mm) > 0.05:
        return settings

    overrides = _NOZZLE_PROFILES[closest]
    if not overrides:
        return settings  # 0.4mm — use base profile as-is

    if "layer_height_mm" in overrides:
        settings.layer_height_mm = overrides["layer_height_mm"]
    if "first_layer_height_mm" in overrides:
        settings.first_layer_height_mm = overrides["first_layer_height_mm"]
    if "print_speed_mm_s" in overrides:
        settings.print_speed_mm_s = overrides["print_speed_mm_s"]
    if "first_layer_speed_mm_s" in overrides:
        settings.first_layer_speed_mm_s = overrides["first_layer_speed_mm_s"]
    if "wall_count" in overrides:
        settings.wall_count = overrides["wall_count"]
    if "top_layers" in overrides:
        settings.top_layers = overrides["top_layers"]
    if "bottom_layers" in overrides:
        settings.bottom_layers = overrides["bottom_layers"]
    if "nozzle_temp_offset_c" in overrides:
        settings.nozzle_temp_c += overrides["nozzle_temp_offset_c"]
    if "fan_speed_percent" in overrides:
        settings.fan_speed_percent = overrides["fan_speed_percent"]
    if "fan_first_layer" in overrides:
        settings.fan_first_layer = overrides["fan_first_layer"]

    return settings
