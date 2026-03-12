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
    )
