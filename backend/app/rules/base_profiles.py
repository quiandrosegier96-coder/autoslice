"""
AutoSlice — Base printer profiles.
Loads conservative safe defaults from data/printers/{id}.json.
"""

import json
from app.config import settings
from app.models.printer import PrinterProfile
from app.models.print_settings import PrintSettings


def load_base_profile(printer: PrinterProfile) -> PrintSettings:
    """
    Load the default PrintSettings for a printer from its JSON definition.
    These are conservative beginner-safe defaults before any adjustments.
    """
    profile_file = settings.printers_dir / f"{printer.id}.json"
    if not profile_file.exists():
        raise FileNotFoundError(f"No profile found for printer: {printer.id}")

    data = json.loads(profile_file.read_text())
    defaults = data.get("default_settings", {})

    return PrintSettings(
        layer_height_mm=defaults["layer_height_mm"],
        first_layer_height_mm=defaults["first_layer_height_mm"],
        wall_count=defaults["wall_count"],
        top_layers=defaults["top_layers"],
        bottom_layers=defaults["bottom_layers"],
        infill_percent=defaults["infill_percent"],
        infill_pattern=defaults["infill_pattern"],
        supports_enabled=defaults["supports_enabled"],
        support_type=defaults["support_type"],
        support_density_percent=defaults["support_density_percent"],
        support_angle_threshold_deg=defaults["support_angle_threshold_deg"],
        brim_enabled=defaults["brim_enabled"],
        brim_width_mm=defaults["brim_width_mm"],
        skirt_loops=defaults["skirt_loops"],
        nozzle_temp_c=defaults["nozzle_temp_c"],
        bed_temp_c=defaults["bed_temp_c"],
        print_speed_mm_s=defaults["print_speed_mm_s"],
        first_layer_speed_mm_s=defaults["first_layer_speed_mm_s"],
        fan_speed_percent=defaults["fan_speed_percent"],
        fan_first_layer=defaults["fan_first_layer"],
        retract_length_mm=defaults.get("retract_length_mm", 0.8),
        retract_speed_mm_s=defaults.get("retract_speed_mm_s", 45),
        z_hop_mm=defaults.get("z_hop_mm", 0.2),
        wipe_on_retract=defaults.get("wipe_on_retract", False),
    )
