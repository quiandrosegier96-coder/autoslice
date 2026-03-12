"""
AutoSlice — Bridge detection.
Detects near-horizontal downward-facing faces that are elevated above the model base.
These are likely bridge regions.

Phase 3: geometric heuristic (no ray casting). Full ray-cast version in Phase 4.
"""

import numpy as np
import trimesh

from app.models.geometry import BridgeReport

# Faces with nz < -0.9 are near-horizontal downward-facing (within ~26° of flat)
_BRIDGE_NORMAL_THRESHOLD = -0.9
# Minimum elevation above model base to count (avoids flagging the actual bottom face)
_BASE_CLEARANCE_MM = 1.0


def detect_bridges(mesh: trimesh.Trimesh) -> BridgeReport:
    """
    Detect likely bridge regions as near-horizontal downward-facing faces
    that are not at the very bottom of the model.

    Span is estimated as the XY diagonal of the bridge face cluster bounding box.
    """
    normals: np.ndarray = mesh.face_normals          # (N, 3)
    centroids: np.ndarray = mesh.triangles_center    # (N, 3)

    min_z = float(mesh.bounds[0][2])

    bridge_mask: np.ndarray = (
        (normals[:, 2] < _BRIDGE_NORMAL_THRESHOLD) &
        (centroids[:, 2] > min_z + _BASE_CLEARANCE_MM)
    )

    if not bridge_mask.any():
        return BridgeReport(has_bridges=False, max_span_mm=0.0)

    bridge_centroids = centroids[bridge_mask]

    # Estimate span as XY bounding box diagonal of all bridge face centroids
    xy_min = bridge_centroids[:, :2].min(axis=0)
    xy_max = bridge_centroids[:, :2].max(axis=0)
    span_mm = round(float(np.linalg.norm(xy_max - xy_min)), 2)

    return BridgeReport(has_bridges=True, max_span_mm=span_mm)
