"""
AutoSlice — Overhang detection.

Convention used throughout:
  - threshold_deg is measured FROM HORIZONTAL (0° = vertical, 90° = flat underside)
  - A face at angle α from horizontal has normal.z = -cos(α)
  - Overhang condition: α < threshold_deg  ↔  normal.z < -cos(threshold_deg)
  - max_angle_deg reported as degrees FROM VERTICAL (0° = no overhang, 90° = flat bottom)
    so it reads intuitively: higher = worse.
"""

import numpy as np
import trimesh

from app.models.geometry import OverhangReport

DEFAULT_THRESHOLD_DEG = 45.0


def detect_overhangs(
    mesh: trimesh.Trimesh,
    threshold_deg: float = DEFAULT_THRESHOLD_DEG,
) -> OverhangReport:
    """
    Detect overhanging faces by analyzing face normals.
    Returns has_overhangs, worst overhang angle, and the ratio of overhang
    surface area to total surface area.
    """
    normals: np.ndarray = mesh.face_normals   # (N, 3)
    areas: np.ndarray = mesh.area_faces        # (N,)
    total_area = float(areas.sum())

    if total_area == 0:
        return OverhangReport(has_overhangs=False, max_angle_deg=0.0, overhang_area_ratio=0.0)

    # Faces whose normal points downward beyond the threshold
    threshold_cos = -np.cos(np.radians(threshold_deg))   # negative value
    overhang_mask: np.ndarray = normals[:, 2] < threshold_cos

    if not overhang_mask.any():
        return OverhangReport(has_overhangs=False, max_angle_deg=0.0, overhang_area_ratio=0.0)

    overhang_nz: np.ndarray = normals[overhang_mask, 2]
    overhang_areas: np.ndarray = areas[overhang_mask]

    # Worst face: most negative nz (closest to pointing straight down)
    min_nz = float(np.clip(overhang_nz.min(), -1.0, 0.0))
    # max_angle_deg from vertical: 90° - arccos(-nz) gives 0° for vertical, 90° for flat bottom
    max_angle_deg = round(90.0 - float(np.degrees(np.arccos(-min_nz))), 2)

    overhang_area_ratio = round(float(overhang_areas.sum()) / total_area, 4)

    return OverhangReport(
        has_overhangs=True,
        max_angle_deg=max_angle_deg,
        overhang_area_ratio=overhang_area_ratio,
    )
