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
        # PLA wants max fan — raise floor to 100%
        "_fan_min": 100,
    },
    FilamentType.PETG: {
        "nozzle_temp_c": 240,
        "bed_temp_c": 80,
        "fan_first_layer": False,
        # PETG max safe fan is 50%; geometry rules may push higher for bridges,
        # but we cap it at 70% to avoid warping (bridges still get more than base)
        "_fan_min": 30,
        "_fan_max": 70,
        # PETG warps — always use brim
        "_force_brim": True,
    },
    FilamentType.TPU: {
        "nozzle_temp_c": 230,
        "bed_temp_c": 40,
        "fan_first_layer": False,
        "_fan_min": 20,
        "_fan_max": 40,
        # TPU is flexible — supports usually cause more harm than good
        "_suppress_supports": True,
        "print_speed_mm_s": 30,
        "first_layer_speed_mm_s": 15,
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
