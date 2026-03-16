"""
AutoSlice — Printer and filament data models.
"""

from dataclasses import dataclass, field
from enum import Enum


class FilamentType(str, Enum):
    PLA = "pla"
    PETG = "petg"
    TPU = "tpu"


@dataclass
class PrinterProfile:
    id: str
    display_name: str
    build_volume_x_mm: int
    build_volume_y_mm: int
    build_volume_z_mm: int
    max_speed_mm_s: int
    nozzle_diameter_mm: float
    supported_filaments: list[FilamentType] = field(default_factory=list)
    max_colors: int = 1
    # Machine limits (optional — exported to 3MF for slicer accuracy)
    max_acceleration_xy: int = 5000
    max_acceleration_z: int = 500
    max_jerk: float = 10.0
    max_speed_z_mm_s: int = 15
    min_layer_height_mm: float = 0.05
    max_layer_height_mm: float = 0.32
