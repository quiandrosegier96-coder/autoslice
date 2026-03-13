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
        "layer_height_mm":         0.1,
        "first_layer_height_mm":   0.2,
        "print_speed_mm_s":        80,
        "first_layer_speed_mm_s":  20,
        "wall_count":              4,
        "top_layers":              7,
        "bottom_layers":           5,
        "nozzle_temp_offset_c":    5,
        "fan_speed_percent":       100,
        "fan_first_layer":         False,
    },
    0.4: {},   # Standard — no overrides
    0.6: {
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
            if trace:
                trace.record(f"nozzle.temp_offset.{tag}",
                             f"{tag} nozzle: temp +{value}°C for small melt zone",
                             "nozzle_temp_c", before, settings.nozzle_temp_c)
        else:
            before = getattr(settings, key)
            setattr(settings, key, value)
            if trace:
                trace.record(f"nozzle.{key}.{tag}",
                             f"{tag} nozzle: {key}={value}",
                             key, before, value)

    return settings
