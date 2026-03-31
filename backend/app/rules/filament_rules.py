"""
AutoSlice — Filament-specific print setting adjustments.
"""

from app.diagnostics.models import DecisionTrace
from app.models.printer import FilamentType
from app.models.print_settings import PrintSettings


_FILAMENT_OVERRIDES: dict[FilamentType, dict] = {
    FilamentType.PLA: {
        "nozzle_temp_c": 200,
        "first_layer_nozzle_temp_c": 220,
        "bed_temp_c": 60,
        "fan_first_layer": False,
        "_fan_min": 100,
        "retract_length_mm": 0.8,
        "retract_speed_mm_s": 45,
        "z_hop_mm": 0.2,
        "wipe_on_retract": False,
        "coast_at_end_mm": 0.0,
        "pressure_advance": 0.04,
        "min_layer_time_s": 8,
        "support_top_z_distance_mm": 0.2,
        "support_bottom_z_distance_mm": 0.2,
        "support_xy_distance_mm": 0.35,
    },
    FilamentType.PETG: {
        "nozzle_temp_c": 240,
        "bed_temp_c": 80,
        "fan_first_layer": False,
        "_fan_min": 30,
        "_fan_max": 70,
        "_force_brim": True,
        # PETG is stringy — longer retract, wipe + coast to prevent ooze blobs
        "retract_length_mm": 1.2,
        "retract_speed_mm_s": 35,
        "z_hop_mm": 0.2,
        "wipe_on_retract": True,
        "coast_at_end_mm": 0.4,
        "pressure_advance": 0.06,
        "min_layer_time_s": 10,
        # PETG bonds to supports — larger gaps for easier removal
        "support_top_z_distance_mm": 0.25,
        "support_bottom_z_distance_mm": 0.25,
        "support_xy_distance_mm": 0.45,
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
        # TPU: minimal retract, no z-hop, PA disabled (flexible material)
        "retract_length_mm": 0.5,
        "retract_speed_mm_s": 20,
        "z_hop_mm": 0.0,
        "wipe_on_retract": False,
        "coast_at_end_mm": 0.0,
        "pressure_advance": 0.0,
        "min_layer_time_s": 12,
        "support_top_z_distance_mm": 0.3,
        "support_bottom_z_distance_mm": 0.3,
        "support_xy_distance_mm": 0.5,
    },
}


def apply_filament_rules(
    settings: PrintSettings,
    filament: FilamentType,
    trace: DecisionTrace | None = None,
) -> PrintSettings:
    overrides = _FILAMENT_OVERRIDES.get(filament, {})
    fil = filament.value

    for key, value in overrides.items():
        if key == "_fan_min":
            before = settings.fan_speed_percent
            settings.fan_speed_percent = max(settings.fan_speed_percent, value)
            if trace:
                trace.record(f"filament.fan_min.{fil}",
                             f"{fil}: fan_min={value}% → raise floor",
                             "fan_speed_percent", before, settings.fan_speed_percent)
        elif key == "_fan_max":
            before = settings.fan_speed_percent
            settings.fan_speed_percent = min(settings.fan_speed_percent, value)
            if trace:
                trace.record(f"filament.fan_max.{fil}",
                             f"{fil}: fan_max={value}% → cap ceiling",
                             "fan_speed_percent", before, settings.fan_speed_percent)
        elif key == "_force_brim":
            before_en = settings.brim_enabled
            before_w  = settings.brim_width_mm
            settings.brim_enabled = True
            if settings.brim_width_mm < 5.0:
                settings.brim_width_mm = 5.0
            if trace:
                trace.record(f"filament.brim.{fil}",
                             f"{fil} warps → force brim",
                             "brim_enabled", before_en, True)
                trace.record(f"filament.brim_width.{fil}",
                             f"{fil} warps → min 5mm brim",
                             "brim_width_mm", before_w, settings.brim_width_mm)
        elif key == "_suppress_supports":
            before = settings.supports_enabled
            settings.supports_enabled = False
            if trace:
                trace.record(f"filament.suppress_supports.{fil}",
                             f"{fil} is flexible — supports cause more harm than good",
                             "supports_enabled", before, False)
        elif not key.startswith("_"):
            before = getattr(settings, key)
            setattr(settings, key, value)
            if trace:
                trace.record(f"filament.{key}.{fil}",
                             f"{fil}: {key}={value}",
                             key, before, value)

    return settings
