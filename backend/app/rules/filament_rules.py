"""
AutoSlice — Filament-specific print setting adjustments.
"""

from app.models.printer import FilamentType
from app.models.print_settings import PrintSettings


_FILAMENT_OVERRIDES: dict[FilamentType, dict] = {
    FilamentType.PLA: {
        "nozzle_temp_c": 220,
        "bed_temp_c": 60,
        "fan_first_layer": False,
        "_fan_min": 100,
        # PLA direct drive: short fast retract, small z-hop
        "retract_length_mm": 0.8,
        "retract_speed_mm_s": 45,
        "z_hop_mm": 0.2,
    },
    FilamentType.PETG: {
        "nozzle_temp_c": 240,
        "bed_temp_c": 80,
        "fan_first_layer": False,
        "_fan_min": 30,
        "_fan_max": 70,
        "_force_brim": True,
        # PETG is stringy — slightly longer retract, slower to avoid blobs
        "retract_length_mm": 1.2,
        "retract_speed_mm_s": 35,
        "z_hop_mm": 0.2,
    },
    FilamentType.TPU: {
        "nozzle_temp_c": 230,
        "bed_temp_c": 40,
        "fan_first_layer": False,
        "_fan_min": 20,
        "_fan_max": 40,
        "_suppress_supports": True,
        "print_speed_mm_s": 30,
        "first_layer_speed_mm_s": 15,
        # TPU: minimal retract (flexible filament can't be yanked back),
        # no z-hop (Z movement can cause blobs with TPU)
        "retract_length_mm": 0.5,
        "retract_speed_mm_s": 20,
        "z_hop_mm": 0.0,
    },
}


def apply_filament_rules(settings: PrintSettings, filament: FilamentType) -> PrintSettings:
    overrides = _FILAMENT_OVERRIDES.get(filament, {})
    for key, value in overrides.items():
        if key == "_fan_min":
            settings.fan_speed_percent = max(settings.fan_speed_percent, value)
        elif key == "_fan_max":
            settings.fan_speed_percent = min(settings.fan_speed_percent, value)
        elif key == "_force_brim":
            settings.brim_enabled = True
            if settings.brim_width_mm < 5.0:
                settings.brim_width_mm = 5.0
        elif key == "_suppress_supports":
            settings.supports_enabled = False
        elif not key.startswith("_"):
            setattr(settings, key, value)
    return settings
