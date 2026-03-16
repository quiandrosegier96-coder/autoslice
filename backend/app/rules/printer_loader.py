"""
AutoSlice — Printer profile loader from JSON data files.
"""

import json
from app.config import settings
from app.models.printer import PrinterProfile, FilamentType


def load_printer_profile(printer_id: str) -> PrinterProfile:
    profile_file = settings.printers_dir / f"{printer_id}.json"
    if not profile_file.exists():
        raise ValueError(f"Unknown printer: '{printer_id}'")
    data = json.loads(profile_file.read_text())
    return PrinterProfile(
        id=data["id"],
        display_name=data["display_name"],
        build_volume_x_mm=data["build_volume_x_mm"],
        build_volume_y_mm=data["build_volume_y_mm"],
        build_volume_z_mm=data["build_volume_z_mm"],
        max_speed_mm_s=data["max_speed_mm_s"],
        nozzle_diameter_mm=data["nozzle_diameter_mm"],
        supported_filaments=[FilamentType(f) for f in data["supported_filaments"]],
        max_colors=data.get("max_colors", 1),
        max_acceleration_xy=data.get("max_acceleration_xy", 5000),
        max_acceleration_z=data.get("max_acceleration_z", 500),
        max_jerk=data.get("max_jerk", 10.0),
        max_speed_z_mm_s=data.get("max_speed_z_mm_s", 15),
        min_layer_height_mm=data.get("min_layer_height_mm", 0.05),
        max_layer_height_mm=data.get("max_layer_height_mm", 0.32),
    )
