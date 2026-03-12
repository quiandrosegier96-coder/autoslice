"""
AutoSlice — Filament-specific print setting adjustments.
"""

from app.models.printer import FilamentType
from app.models.print_settings import PrintSettings


_FILAMENT_OVERRIDES: dict[FilamentType, dict] = {
    FilamentType.PLA: {
        "nozzle_temp_c": 220,
        "bed_temp_c": 60,
        "fan_speed_percent": 100,
        "fan_first_layer": False,
    },
    FilamentType.PETG: {
        "nozzle_temp_c": 240,
        "bed_temp_c": 80,
        "fan_speed_percent": 50,
        "fan_first_layer": False,
    },
    FilamentType.TPU: {
        "nozzle_temp_c": 230,
        "bed_temp_c": 40,
        "fan_speed_percent": 30,
        "fan_first_layer": False,
        "print_speed_mm_s": 30,
        "first_layer_speed_mm_s": 15,
    },
}


def apply_filament_rules(settings: PrintSettings, filament: FilamentType) -> PrintSettings:
    overrides = _FILAMENT_OVERRIDES.get(filament, {})
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings
