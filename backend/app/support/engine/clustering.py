"""
AutoSlice — Tree Support Engine: Spatial Clustering

Step 2: Group nearby overhang faces into spatially connected islands.

Algorithm:
  1. Assign each face centroid to a 3-D grid cell
     (cell key = floor(pos / cellSize)).
  2. Build adjacency from 26-neighbor 3-D Moore neighbourhood.
  3. Union-Find merges adjacent non-empty cells into connected components.
  4. Each component → one SupportCluster with:
       - area-weighted centroid
       - average downward normal
       - tip position (centroid offset toward the underside)
       - severity classification

No external dependencies required.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

from .models import EngineConfig, OverhangFace, SupportCluster, Vec3


# ── Union-Find ────────────────────────────────────────────────────────────────

class _UF:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank   = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


# ── Main clustering function ───────────────────────────────────────────────────

def cluster_overhangs(
    faces:  List[OverhangFace],
    config: EngineConfig,
) -> List[SupportCluster]:
    """
    Cluster overhang faces into spatially connected islands.

    Returns a list of SupportCluster objects sorted by area (largest first).
    """
    if not faces:
        return []

    cell = config.cluster_cell_mm

    # ── 1. Assign grid cells ────────────────────────────────────────────────
    CellKey = Tuple[int, int, int]

    def to_cell(v: Vec3) -> CellKey:
        return (
            math.floor(v.x / cell),
            math.floor(v.y / cell),
            math.floor(v.z / cell),
        )

    cell_to_face_ids: Dict[CellKey, List[int]] = {}
    face_cells: List[CellKey] = []

    for i, f in enumerate(faces):
        ck = to_cell(f.centroid)
        face_cells.append(ck)
        cell_to_face_ids.setdefault(ck, []).append(i)

    cell_keys  = list(cell_to_face_ids.keys())
    key_to_idx = {k: i for i, k in enumerate(cell_keys)}
    uf         = _UF(len(cell_keys))

    # ── 2. Merge adjacent cells (26-neighbour) ───────────────────────────────
    for gx, gy, gz in cell_keys:
        my_idx = key_to_idx[(gx, gy, gz)]
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                for dz in range(-1, 2):
                    if dx == dy == dz == 0:
                        continue
                    nb = (gx + dx, gy + dy, gz + dz)
                    nb_idx = key_to_idx.get(nb)
                    if nb_idx is not None:
                        uf.union(my_idx, nb_idx)

    # ── 3. Group faces by component ──────────────────────────────────────────
    component: Dict[int, List[int]] = {}
    for fi, ck in enumerate(face_cells):
        root = uf.find(key_to_idx[ck])
        component.setdefault(root, []).append(fi)

    # ── 4. Build clusters ────────────────────────────────────────────────────
    clusters: List[SupportCluster] = []
    cluster_id = 0

    for face_indices in component.values():
        cluster_faces = [faces[i] for i in face_indices]
        total_area    = sum(f.area for f in cluster_faces)

        if total_area < config.min_cluster_area_mm2:
            continue

        # Area-weighted centroid
        cx = cy = cz = 0.0
        for f in cluster_faces:
            cx += f.centroid.x * f.area
            cy += f.centroid.y * f.area
            cz += f.centroid.z * f.area
        centroid = Vec3(cx / total_area, cy / total_area, cz / total_area)

        # Average downward normal
        nx = ny = nz = 0.0
        for f in cluster_faces:
            nx += f.normal.x
            ny += f.normal.y
            nz += f.normal.z
        n_len = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        avg_normal = Vec3(nx / n_len, ny / n_len, nz / n_len)

        # Tip position: centroid shifted slightly along avg_normal direction
        # (points away from the underside, so we go in the normal direction
        # which is downward — that puts the tip just below the surface)
        tip = Vec3(
            centroid.x + avg_normal.x * config.z_distance_mm,
            centroid.y + avg_normal.y * config.z_distance_mm,
            centroid.z + avg_normal.z * config.z_distance_mm,
        )

        # Bounding box
        all_centroids = [f.centroid for f in cluster_faces]
        bmin = Vec3(
            min(v.x for v in all_centroids),
            min(v.y for v in all_centroids),
            min(v.z for v in all_centroids),
        )
        bmax = Vec3(
            max(v.x for v in all_centroids),
            max(v.y for v in all_centroids),
            max(v.z for v in all_centroids),
        )

        # Severity
        severity = _severity(total_area)

        clusters.append(SupportCluster(
            id           = cluster_id,
            centroid     = centroid,
            area         = total_area,
            face_count   = len(cluster_faces),
            tip_position = tip,
            avg_normal   = avg_normal,
            bbox_min     = bmin,
            bbox_max     = bmax,
            severity     = severity,
        ))
        cluster_id += 1

    clusters.sort(key=lambda c: c.area, reverse=True)
    return clusters


def _severity(area: float) -> str:
    if area > 200.0:
        return "critical"
    if area > 80.0:
        return "severe"
    if area > 25.0:
        return "moderate"
    return "minor"


# ── Secondary XY grouping (for trunk sharing) ─────────────────────────────────

def group_clusters_by_xy(
    clusters: List[SupportCluster],
    radius:   float,
) -> List[List[SupportCluster]]:
    """
    Group SupportClusters whose XY centroids are within `radius` of each other.
    Each group will share a single trunk root.
    """
    if not clusters:
        return []

    used   = [False] * len(clusters)
    groups: List[List[SupportCluster]] = []

    for i, ci in enumerate(clusters):
        if used[i]:
            continue
        group = [ci]
        used[i] = True
        for j in range(i + 1, len(clusters)):
            if used[j]:
                continue
            dxy = ci.centroid.xy_dist(clusters[j].centroid)
            if dxy <= radius:
                group.append(clusters[j])
                used[j] = True
        groups.append(group)

    return groups
