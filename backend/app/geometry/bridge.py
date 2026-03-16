"""
AutoSlice — Bridge detection.
Detects near-horizontal downward-facing faces that are elevated above the model base.
These are likely bridge regions.

Improvement over Phase 3: bridge faces are clustered by mesh face adjacency so that
each independent bridge region gets its own span measurement. max_span_mm is the span
of the LARGEST cluster, preventing false inflation when bridges are on opposite ends
of the model.
"""

from collections import defaultdict

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

    Bridge faces are clustered by adjacency; each independent cluster gets
    its own span estimate. Reports the maximum cluster span, total bridge area,
    and cluster count.
    """
    normals: np.ndarray   = mesh.face_normals        # (N, 3)
    centroids: np.ndarray = mesh.triangles_center    # (N, 3)
    areas: np.ndarray     = mesh.area_faces          # (N,)

    min_z = float(mesh.bounds[0][2])

    bridge_mask: np.ndarray = (
        (normals[:, 2] < _BRIDGE_NORMAL_THRESHOLD) &
        (centroids[:, 2] > min_z + _BASE_CLEARANCE_MM)
    )

    if not bridge_mask.any():
        return BridgeReport(has_bridges=False, max_span_mm=0.0,
                            bridge_area_mm2=0.0, cluster_count=0)

    bridge_face_indices = np.where(bridge_mask)[0]
    bridge_area_mm2 = round(float(areas[bridge_mask].sum()), 2)

    # Cluster bridge faces by mesh face adjacency (shared edges)
    clusters = _cluster_faces(mesh, bridge_face_indices)

    # Compute XY span for each cluster
    max_span = 0.0
    for cluster_indices in clusters.values():
        cluster_centroids = centroids[list(cluster_indices)]
        xy_min = cluster_centroids[:, :2].min(axis=0)
        xy_max = cluster_centroids[:, :2].max(axis=0)
        span = float(np.linalg.norm(xy_max - xy_min))
        if span > max_span:
            max_span = span

    return BridgeReport(
        has_bridges=True,
        max_span_mm=round(max_span, 2),
        bridge_area_mm2=bridge_area_mm2,
        cluster_count=len(clusters),
    )


def _cluster_faces(
    mesh: trimesh.Trimesh,
    face_indices: np.ndarray,
) -> dict[int, set]:
    """
    Group face_indices into connected clusters using mesh face adjacency.
    Returns a dict mapping cluster-root → set of face indices.
    Uses union-find with path compression.
    """
    face_set = set(face_indices.tolist())

    # Build adjacency restricted to our face subset
    # mesh.face_adjacency is an (M, 2) array of adjacent face index pairs
    adj = mesh.face_adjacency  # (M, 2)
    # Keep only pairs where BOTH faces are bridge faces
    in_set_mask = np.isin(adj[:, 0], face_indices) & np.isin(adj[:, 1], face_indices)
    bridge_adj = adj[in_set_mask]

    # Union-Find
    parent = {int(f): int(f) for f in face_indices}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]   # path compression
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for a, b in bridge_adj:
        union(int(a), int(b))

    # Group by root
    clusters: dict[int, set] = defaultdict(set)
    for f in face_set:
        clusters[find(f)].add(f)

    return clusters
