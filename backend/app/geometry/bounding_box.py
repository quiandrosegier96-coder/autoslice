"""
AutoSlice — Bounding box computation.
"""

import trimesh

from app.models.geometry import BoundingBox


def compute_bounding_box(mesh: trimesh.Trimesh) -> BoundingBox:
    """
    Compute axis-aligned bounding box dimensions and mesh volume.
    Volume is approximate for non-watertight meshes.
    """
    extents = mesh.extents          # [x_size, y_size, z_size] in mm
    volume_mm3 = abs(float(mesh.volume))
    volume_cm3 = volume_mm3 / 1000.0

    return BoundingBox(
        x_mm=round(float(extents[0]), 3),
        y_mm=round(float(extents[1]), 3),
        z_mm=round(float(extents[2]), 3),
        volume_cm3=round(volume_cm3, 4),
    )
