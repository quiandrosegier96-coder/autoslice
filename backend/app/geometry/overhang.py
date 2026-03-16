"""
AutoSlice — Overhang detection.

Convention used throughout:
  - threshold_deg is measured FROM HORIZONTAL (0° = vertical, 90° = flat underside)
  - A face at angle α from horizontal has normal.z = -cos(α)
  - Overhang condition: α < threshold_deg  ↔  normal.z < -cos(threshold_deg)
  - max_angle_deg reported as degrees FROM VERTICAL (0° = no overhang, 90° = flat bottom)
    so it reads intuitively: higher = worse.

Severity zones (all angles FROM VERTICAL):
  mild     45–55°  — printable with most printers without support
  moderate 55–65°  — borderline; support recommended
  severe   65°+    — always requires support
"""

import numpy as np
import trimesh

from app.models.geometry import OverhangReport

DEFAULT_THRESHOLD_DEG = 45.0
_MODERATE_DEG = 55.0
_SEVERE_DEG   = 65.0


def detect_overhangs(
    mesh: trimesh.Trimesh,
    threshold_deg: float = DEFAULT_THRESHOLD_DEG,
) -> OverhangReport:
    """
    Detect overhanging faces by analysing face normals.
    Returns has_overhangs, worst overhang angle, the ratio of overhang
    surface area to total surface area, per-severity-zone ratios, and
    the estimated XY-projected area that would need support.
    """
    normals: np.ndarray = mesh.face_normals   # (N, 3)
    areas: np.ndarray   = mesh.area_faces      # (N,)
    total_area = float(areas.sum())

    if total_area == 0:
        return OverhangReport(has_overhangs=False, max_angle_deg=0.0,
                              overhang_area_ratio=0.0)

    # nz thresholds (negative because normals point downward for overhangs)
    cos_mild     = -np.cos(np.radians(threshold_deg))   # 45° threshold
    cos_moderate = -np.cos(np.radians(_MODERATE_DEG))   # 55°
    cos_severe   = -np.cos(np.radians(_SEVERE_DEG))     # 65°

    # Overall overhang mask (any face beyond 45°)
    overhang_mask: np.ndarray = normals[:, 2] < cos_mild

    if not overhang_mask.any():
        return OverhangReport(has_overhangs=False, max_angle_deg=0.0,
                              overhang_area_ratio=0.0)

    nz_all = normals[:, 2]

    # Zone masks — all zones are exclusive to avoid double-counting
    mild_mask     = overhang_mask & (nz_all >= cos_moderate)          # 45–55°
    moderate_mask = overhang_mask & (nz_all < cos_moderate) & (nz_all >= cos_severe)  # 55–65°
    severe_mask   = overhang_mask & (nz_all < cos_severe)             # 65°+

    overhang_areas = areas[overhang_mask]
    mild_areas     = areas[mild_mask]
    moderate_areas = areas[moderate_mask]
    severe_areas   = areas[severe_mask]

    # Worst face: most negative nz → highest angle from vertical
    overhang_nz = nz_all[overhang_mask]
    min_nz = float(np.clip(overhang_nz.min(), -1.0, 0.0))
    # max_angle_deg: 0° = vertical, 90° = flat underside
    max_angle_deg = round(90.0 - float(np.degrees(np.arccos(-min_nz))), 2)

    overhang_area_ratio  = round(float(overhang_areas.sum()) / total_area, 4)
    mild_area_ratio      = round(float(mild_areas.sum())     / total_area, 4)
    moderate_area_ratio  = round(float(moderate_areas.sum()) / total_area, 4)
    severe_area_ratio    = round(float(severe_areas.sum())   / total_area, 4)

    # Estimated support area: XY-projected area of overhang faces
    # For a face with normal.z = nz, its XY projection = face_area * |nz|
    support_area_mm2 = round(
        float(np.sum(areas[overhang_mask] * np.abs(nz_all[overhang_mask]))), 2
    )

    return OverhangReport(
        has_overhangs=True,
        max_angle_deg=max_angle_deg,
        overhang_area_ratio=overhang_area_ratio,
        mild_area_ratio=mild_area_ratio,
        moderate_area_ratio=moderate_area_ratio,
        severe_area_ratio=severe_area_ratio,
        estimated_support_area_mm2=support_area_mm2,
    )
