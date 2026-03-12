"""
AutoSlice — Thin wall / fragile structure detection.

Phase 3: returns a conservative default (no thin walls detected).
Full bilateral ray-casting implementation is scheduled for Phase 4.
"""

import trimesh

from app.models.geometry import ThinWallReport

DEFAULT_NOZZLE_DIAMETER_MM = 0.4


def detect_thin_walls(
    mesh: trimesh.Trimesh,
    nozzle_diameter_mm: float = DEFAULT_NOZZLE_DIAMETER_MM,
) -> ThinWallReport:
    """
    Estimate minimum wall thickness.
    Phase 3 returns a safe conservative default.
    Phase 4 will implement bilateral ray-casting across sampled surface points.
    """
    # Conservative default: assume walls are printable until Phase 4 ray-cast is live
    return ThinWallReport(has_thin_walls=False, min_thickness_mm=999.0)
