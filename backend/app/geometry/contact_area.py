"""
AutoSlice — Contact area and height-to-base-ratio computation.

contact_area_mm2:
  XY-projected area of faces touching (or near) the build plate.
  High contact = good adhesion. Low contact = brim needed.

height_to_base_ratio (HBR):
  z_height / sqrt(contact_area_mm2)
  < 1.5  → stable
  1.5-3  → moderate
  3-5    → tall/thin — brim recommended
  > 5    → very unstable — brim + slow speed mandatory
"""

import math

import numpy as np
import trimesh


def compute_contact_metrics(mesh: trimesh.Trimesh) -> tuple[float, float]:
    """
    Returns (contact_area_mm2, height_to_base_ratio).
    """
    bounds = mesh.bounds
    min_z = float(bounds[0][2])
    max_z = float(bounds[1][2])
    height = max_z - min_z

    normals: np.ndarray = mesh.face_normals      # (N, 3)
    centroids: np.ndarray = mesh.triangles_center  # (N, 3)
    areas: np.ndarray = mesh.area_faces            # (N,)

    # Accept faces within 0.5mm of Z_min OR within 2% of total height — whichever is larger
    z_thresh = min_z + max(0.5, height * 0.02)

    # Downward-facing faces near the base (nz < -0.3 means at least 17° from vertical)
    bottom_mask = (centroids[:, 2] <= z_thresh) & (normals[:, 2] < -0.3)

    if not bottom_mask.any():
        # Fallback: all faces near the base regardless of normal direction
        bottom_mask = centroids[:, 2] <= z_thresh

    if bottom_mask.any():
        # XY-projected area = face_area * |nz|  (cos projection onto horizontal plane)
        b_areas = areas[bottom_mask]
        b_nz = np.abs(normals[bottom_mask, 2])
        contact_area = float(np.sum(b_areas * b_nz))
    else:
        # No faces found at all — use XY bounding box as rough estimate
        contact_area = float(mesh.extents[0]) * float(mesh.extents[1]) * 0.3

    contact_area = max(1.0, round(contact_area, 2))
    hbr = round(height / math.sqrt(contact_area), 4)

    return contact_area, hbr
