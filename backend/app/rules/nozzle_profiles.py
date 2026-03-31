"""
AutoSlice — Nozzle-size specific profile adjustments.

Each nozzle size has different optimal settings:
- 0.2mm: very fine detail, slow, thin layers, slightly hotter
- 0.4mm: standard (no overrides — base profile is designed for this)
- 0.6mm: fast, thick layers
"""

from app.diagnostics.models import DecisionTrace
from app.models.print_settings import PrintSettings


_NOZZLE_PROFILES: dict[float, dict] = {
    0.2: {
        # Fine detail — slow, thin layers, extra walls + top layers, slightly hotter
        "layer_height_mm":         0.1,
        "first_layer_height_mm":   0.2,
        "print_speed_mm_s":        80,
        "first_layer_speed_mm_s":  20,
        "wall_count":              4,
        "top_layers":              7,
        "bottom_layers":           5,
        "nozzle_temp_offset_c":    5,   # tiny melt zone needs hotter to flow properly
        "fan_speed_percent":       100,
        "fan_first_layer":         False,
    },
    0.4: {},   # Standard — base profile is tuned for this; no overrides needed
    0.6: {
        # Draft / fast — thicker layers, fewer shells, slightly reduced fan
        "layer_height_mm":         0.35,
        "first_layer_height_mm":   0.4,
        "print_speed_mm_s":        250,
        "first_layer_speed_mm_s":  40,
        "wall_count":              3,
        "top_layers":              4,
        "bottom_layers":           3,
        "nozzle_temp_offset_c":    0,
        "fan_speed_percent":       80,
        "fan_first_layer":         False,
    },
    0.8: {
        # Fast / structural — very thick layers, 2 walls sufficient (line width covers more),
        # hotter to keep high volumetric flow, reduced fan for layer bonding
        "layer_height_mm":         0.45,
        "first_layer_height_mm":   0.5,
        "print_speed_mm_s":        300,
        "first_layer_speed_mm_s":  45,
        "wall_count":              2,
        "top_layers":              3,
        "bottom_layers":           3,
        "nozzle_temp_offset_c":    5,   # larger melt zone: slight temp boost aids flow
        "fan_speed_percent":       70,
        "fan_first_layer":         False,
    },
    1.0: {
        # Extra thick / vase-mode / rapid prototyping — maximum layer height,
        # minimum shells, hottest to sustain very high volumetric throughput
        "layer_height_mm":         0.55,
        "first_layer_height_mm":   0.6,
        "print_speed_mm_s":        300,
        "first_layer_speed_mm_s":  50,
        "wall_count":              2,
        "top_layers":              2,
        "bottom_layers":           2,
        "nozzle_temp_offset_c":    10,  # 1mm nozzle needs sustained high temp
        "fan_speed_percent":       60,
        "fan_first_layer":         False,
    },
}


def apply_nozzle_profile(
    settings: PrintSettings,
    nozzle_size_mm: float,
    trace: DecisionTrace | None = None,
) -> PrintSettings:
    closest = min(_NOZZLE_PROFILES.keys(), key=lambda k: abs(k - nozzle_size_mm))
    if abs(closest - nozzle_size_mm) > 0.05:
        return settings

    overrides = _NOZZLE_PROFILES[closest]
    if not overrides:
        return settings

    tag = f"{nozzle_size_mm}mm"

    for key, value in overrides.items():
        if key == "nozzle_temp_offset_c":
            before = settings.nozzle_temp_c
            settings.nozzle_temp_c += value
            # Apply offset to first-layer temp too if it's set separately
            if settings.first_layer_nozzle_temp_c:
                settings.first_layer_nozzle_temp_c += value
            if trace:
                trace.record(f"nozzle.temp_offset.{tag}",
                             f"{tag} nozzle: temp +{value}°C for small melt zone",
                             "nozzle_temp_c", before, settings.nozzle_temp_c)
        else:
            before = getattr(settings, key, None)
            setattr(settings, key, value)
            if trace:
                trace.record(f"nozzle.{key}.{tag}",
                             f"{tag} nozzle: {key}={value}",
                             key, before, value)

    return settings
