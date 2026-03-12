"""
AutoSlice — PrintSettings data model.
The full set of slicer parameters produced by the Rules Engine.
"""

from dataclasses import dataclass, field


@dataclass
class PrintSettings:
    # --- Layer ---
    layer_height_mm: float
    first_layer_height_mm: float

    # --- Walls / shells ---
    wall_count: int
    top_layers: int
    bottom_layers: int

    # --- Infill ---
    infill_percent: int
    infill_pattern: str          # e.g. "gyroid", "grid", "honeycomb"

    # --- Supports ---
    supports_enabled: bool
    support_type: str            # "normal" | "tree" | "none"
    support_density_percent: int
    support_angle_threshold_deg: int

    # --- Adhesion ---
    brim_enabled: bool
    brim_width_mm: float
    skirt_loops: int

    # --- Temperatures ---
    nozzle_temp_c: int
    bed_temp_c: int

    # --- Speed ---
    print_speed_mm_s: int
    first_layer_speed_mm_s: int

    # --- Cooling ---
    fan_speed_percent: int
    fan_first_layer: bool

    # --- Hardware selection ---
    nozzle_size_mm: float = 0.4
    nozzle_type: str = "brass"
    filament_diameter_mm: float = 1.75
    build_plate: str = "smooth"
    flush_volume_mm3: float = 3.0

    # --- Multi-color (ACE Pro / ACE Pro 2) ---
    color_count: int = 1
    filament_colors: list = field(default_factory=list)   # hex e.g. ["#FF0000", "#00FF00"]
    filament_types: list = field(default_factory=list)    # per-slot e.g. ["pla", "pla"]
