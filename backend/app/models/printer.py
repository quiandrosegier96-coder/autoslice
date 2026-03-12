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
