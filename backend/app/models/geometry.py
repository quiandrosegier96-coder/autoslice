"""
AutoSlice — Geometry analysis data models.
These are produced by the Geometry Analysis layer and passed to Normalization.
"""

from dataclasses import dataclass, field


@dataclass
class BoundingBox:
    x_mm: float
    y_mm: float
    z_mm: float
    volume_cm3: float


@dataclass
class OverhangReport:
    has_overhangs: bool
    max_angle_deg: float        # worst-case overhang angle found
    overhang_area_ratio: float  # ratio of overhanging faces to total surface area
    # Severity zones (45–55° mild, 55–65° moderate, 65°+ severe)
    mild_area_ratio: float = 0.0        # 45–55° from vertical
    moderate_area_ratio: float = 0.0    # 55–65° from vertical
    severe_area_ratio: float = 0.0      # 65°+ from vertical (near-flat underside)
    estimated_support_area_mm2: float = 0.0  # XY-projected area needing support


@dataclass
class BridgeReport:
    has_bridges: bool
    max_span_mm: float
    bridge_area_mm2: float = 0.0   # total downward-facing elevated area
    cluster_count: int = 0         # number of independent bridge regions


@dataclass
class ThinWallReport:
    has_thin_walls: bool
    min_thickness_mm: float


@dataclass
class GeometryAnalysis:
    bounding_box: BoundingBox
    part_count: int
    mesh_is_watertight: bool
    estimated_volume_cm3: float
    overhang: OverhangReport = field(default_factory=lambda: OverhangReport(False, 0.0, 0.0))
    bridge: BridgeReport = field(default_factory=lambda: BridgeReport(False, 0.0))
    thin_wall: ThinWallReport = field(default_factory=lambda: ThinWallReport(False, 999.0))
    # Extended fields — computed by analyzer
    surface_area_mm2: float = 0.0       # total mesh surface area
    contact_area_mm2: float = 0.0       # XY-projected area touching the build plate
    height_to_base_ratio: float = 0.0   # z / sqrt(contact_area) — stability indicator
    slenderness_ratio: float = 0.0      # z / min(x, y) — raw aspect ratio
    center_of_mass_z_ratio: float = 0.5 # CoM z / height (0=bottom, 1=top; >0.6 = top-heavy)
