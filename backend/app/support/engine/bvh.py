"""
AutoSlice — Tree Support Engine: BVH (Bounding Volume Hierarchy)

Axis-Aligned Bounding Box BVH with:
  - Median-split construction (O(n log n))
  - Möller–Trumbore ray-triangle intersection
  - AABB slab ray intersection
  - Segment collision query (for branch collision avoidance)

Uses numpy for all vector arithmetic; the build pass is the only Python loop.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np


# ── AABB ──────────────────────────────────────────────────────────────────────

class AABB:
    __slots__ = ("mn", "mx")

    def __init__(self, mn: np.ndarray, mx: np.ndarray) -> None:
        self.mn = mn  # shape (3,)
        self.mx = mx

    @staticmethod
    def from_triangles(vertices: np.ndarray, faces_idx: np.ndarray,
                       faces: np.ndarray) -> "AABB":
        tri_verts = vertices[faces[faces_idx].reshape(-1)]
        return AABB(tri_verts.min(axis=0), tri_verts.max(axis=0))

    def expand(self, margin: float) -> "AABB":
        return AABB(self.mn - margin, self.mx + margin)

    def surface_area(self) -> float:
        d = self.mx - self.mn
        return float(2.0 * (d[0] * d[1] + d[1] * d[2] + d[2] * d[0]))

    def intersect_ray(self, origin: np.ndarray, inv_dir: np.ndarray) -> bool:
        """Slab method. Returns True if ray hits the AABB."""
        t1 = (self.mn - origin) * inv_dir
        t2 = (self.mx - origin) * inv_dir
        tmin = np.minimum(t1, t2).max()
        tmax = np.maximum(t1, t2).min()
        return bool(tmax >= max(tmin, 0.0))


# ── BVH nodes ─────────────────────────────────────────────────────────────────

class _BVHLeaf:
    __slots__ = ("aabb", "indices")

    def __init__(self, aabb: AABB, indices: np.ndarray) -> None:
        self.aabb    = aabb
        self.indices = indices   # face indices (int array)


class _BVHInner:
    __slots__ = ("aabb", "left", "right")

    def __init__(self, aabb: AABB, left, right) -> None:
        self.aabb  = aabb
        self.left  = left
        self.right = right


# ── BVH ───────────────────────────────────────────────────────────────────────

class BVH:
    """
    Bounding Volume Hierarchy for a triangle mesh.

    Parameters
    ----------
    vertices : (N, 3) float32 array
    faces    : (M, 3) int32 array  (triangle vertex indices)
    leaf_max : max triangles per leaf (default 6)
    """

    def __init__(self, vertices: np.ndarray, faces: np.ndarray,
                 leaf_max: int = 6) -> None:
        self._v        = np.asarray(vertices, dtype=np.float64)
        self._f        = np.asarray(faces,    dtype=np.int32)
        self._leaf_max = leaf_max

        v0 = self._v[self._f[:, 0]]
        v1 = self._v[self._f[:, 1]]
        v2 = self._v[self._f[:, 2]]
        self._centroids = (v0 + v1 + v2) / 3.0

        all_idx = np.arange(len(self._f), dtype=np.int32)
        self._root = self._build(all_idx, depth=0)

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self, indices: np.ndarray, depth: int):
        aabb = AABB.from_triangles(self._v, indices, self._f)

        if len(indices) <= self._leaf_max or depth > 22:
            return _BVHLeaf(aabb, indices)

        # Choose split axis: longest AABB dimension
        span = aabb.mx - aabb.mn
        axis = int(np.argmax(span))

        centroids = self._centroids[indices, axis]
        median    = float(np.median(centroids))

        left_mask  = centroids <= median
        right_mask = ~left_mask

        # Degenerate: all triangles on one side
        if left_mask.sum() == 0 or right_mask.sum() == 0:
            return _BVHLeaf(aabb, indices)

        left  = self._build(indices[left_mask],  depth + 1)
        right = self._build(indices[right_mask], depth + 1)
        return _BVHInner(aabb, left, right)

    # ── Ray cast ──────────────────────────────────────────────────────────────

    def ray_cast(
        self,
        origin:    np.ndarray,
        direction: np.ndarray,
        max_dist:  float = np.inf,
        skip_face: int   = -1,
    ) -> Optional[Tuple[float, int]]:
        """
        Nearest intersection of a ray with the mesh.

        Returns (distance, face_index) or None.
        """
        origin    = np.asarray(origin,    dtype=np.float64)
        direction = np.asarray(direction, dtype=np.float64)

        # Avoid division by zero in inv_dir
        with np.errstate(divide="ignore", invalid="ignore"):
            inv_dir = np.where(
                np.abs(direction) > 1e-12,
                1.0 / direction,
                np.sign(direction) * 1e15,
            )

        best_t   = max_dist
        best_idx = -1

        stack: List = [self._root]
        while stack:
            node = stack.pop()
            if not node.aabb.intersect_ray(origin, inv_dir):
                continue

            if isinstance(node, _BVHLeaf):
                for fi in node.indices:
                    if fi == skip_face:
                        continue
                    t = _moller_trumbore(origin, direction,
                                        self._v[self._f[fi]])
                    if t is not None and t < best_t:
                        best_t   = t
                        best_idx = fi
            else:
                stack.append(node.left)
                stack.append(node.right)

        return (best_t, best_idx) if best_idx >= 0 else None

    # ── Segment intersection ───────────────────────────────────────────────────

    def segment_intersects(
        self,
        a:      np.ndarray,
        b:      np.ndarray,
        margin: float = 0.0,
    ) -> bool:
        """
        Returns True if the segment A→B intersects any mesh triangle.

        `margin` shrinks the effective segment length on both ends to avoid
        false positives at endpoints.
        """
        a = np.asarray(a, dtype=np.float64)
        b = np.asarray(b, dtype=np.float64)
        d = b - a
        length = float(np.linalg.norm(d))
        if length < 1e-6:
            return False
        direction = d / length
        start     = a + direction * margin
        eff_len   = length - 2.0 * margin
        if eff_len <= 0.0:
            return False
        result = self.ray_cast(start, direction, max_dist=eff_len)
        return result is not None

    # ── Multiple downward ray samples ─────────────────────────────────────────

    def any_geometry_below(
        self,
        point:       np.ndarray,
        max_depth:   float,
        sample_r:    float = 0.0,
        n_samples:   int   = 1,
    ) -> bool:
        """
        Return True if any mesh geometry is found within max_depth below
        `point` (gravity = -Z).  Optionally sample a small circle.
        """
        down = np.array([0.0, 0.0, -1.0])
        pts  = [point]
        if sample_r > 0.0 and n_samples > 1:
            for k in range(n_samples - 1):
                angle = 2.0 * np.pi * k / (n_samples - 1)
                offset = np.array([np.cos(angle), np.sin(angle), 0.0]) * sample_r
                pts.append(point + offset)

        for p in pts:
            p_off = p + np.array([0.0, 0.0, 0.05])  # avoid self-hit
            if self.ray_cast(p_off, down, max_dist=max_depth) is not None:
                return True
        return False


# ── Möller–Trumbore ray-triangle intersection ─────────────────────────────────

def _moller_trumbore(
    origin:    np.ndarray,
    direction: np.ndarray,
    tri:       np.ndarray,   # (3, 3) — three vertices
    eps:       float = 1e-8,
) -> Optional[float]:
    """
    Returns distance `t` along the ray, or None if no intersection.
    """
    e1 = tri[1] - tri[0]
    e2 = tri[2] - tri[0]
    h  = np.cross(direction, e2)
    a  = np.dot(e1, h)

    if abs(a) < eps:
        return None   # ray parallel to triangle

    f = 1.0 / a
    s = origin - tri[0]
    u = f * np.dot(s, h)
    if u < 0.0 or u > 1.0:
        return None

    q = np.cross(s, e1)
    v = f * np.dot(direction, q)
    if v < 0.0 or u + v > 1.0:
        return None

    t = f * np.dot(e2, q)
    return float(t) if t > eps else None
