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

    # --- Retraction ---
    retract_length_mm: float = 0.8    # direct drive default
    retract_speed_mm_s: int = 45
    z_hop_mm: float = 0.2
    wipe_on_retract: bool = False     # wipe nozzle before retract (reduces blobs)
    coast_at_end_mm: float = 0.0      # stop extruding N mm before end (reduces ooze)

    # --- Pressure advance ---
    pressure_advance: float = 0.04   # per-filament PA value; 0.0 = disabled

    # --- Support gaps ---
    support_top_z_distance_mm: float = 0.2    # gap above support (smaller = better surface but harder to remove)
    support_bottom_z_distance_mm: float = 0.2
    support_xy_distance_mm: float = 0.35      # horizontal gap (smaller = more coverage, harder to remove)

    # --- Cooling ---
    min_layer_time_s: int = 8         # slow down if layer prints faster than this

    # --- Cooling ---
    fan_speed_percent: int
    fan_first_layer: bool

    # --- Support interface ---
    support_interface_enabled: bool = False
    support_interface_layers: int = 2        # top + bottom interface layers
    support_interface_pattern: str = "concentric"  # concentric | rectilinear

    # --- Top surface quality ---
    ironing_enabled: bool = False            # smooth flat tops by re-tracing
    top_surface_pattern: str = "monotonic"  # monotonic | concentric | default

    # --- Seam ---
    seam_position: str = "aligned"          # aligned | rear | random | nearest

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
