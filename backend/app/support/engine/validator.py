"""
AutoSlice — Tree Support Validator (Zero Tolerance)

Every support segment must pass ALL of the following before it is kept:

  Rule 1 — NO INTERSECTIONS
      Full ray cast from start → end with zero endpoint skip.
      Any mesh hit → reject.

  Rule 2 — NO INTERNAL POINTS
      N evenly-spaced samples along the segment are tested via trimesh
      winding-number inside check.
      Any sample inside the mesh → reject.

  Rule 3 — CLEARANCE ENFORCED
      Every sample must be at least CLEARANCE_MM from the nearest mesh
      surface.  Proximity is computed via trimesh closest-point.
      Any sample closer than clearance → reject.

  Rule 4 — HARD FAIL LOGIC
      If a check is ambiguous or raises an exception → reject.
      We prefer missing supports over intersecting supports.

Public API
----------
validate_segment_strict(pa, pb, bvh, mesh_tm, clearance, n_samples) → bool
filter_valid_segments(segments, nodes, bvh, mesh_tm, clearance, n_samples)
      → (nodes, segments)
is_point_outside_mesh(point, mesh_tm, clearance) → bool
tag_debug(segments, nodes, bvh, mesh_tm, clearance, n_samples)
      → dict[int, str]   ("valid" | "colliding" | "internal" | "too_close")
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from .bvh    import BVH
from .models import SupportNode, SupportSegment

log = logging.getLogger(__name__)

# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_CLEARANCE_MM = 0.8    # mm — minimum distance to mesh surface
DEFAULT_N_SAMPLES    = 24     # sample count per segment


# ── Point-level checks ────────────────────────────────────────────────────────

def is_point_outside_mesh(
    point:     np.ndarray,      # shape (3,)
    mesh_tm,                    # trimesh.Trimesh
    clearance: float = 0.0,
) -> bool:
    """
    Return True iff `point` is outside the mesh and at least `clearance` mm
    from every surface triangle.

    On any exception → returns False (conservative: treat as invalid).
    """
    try:
        inside = bool(mesh_tm.contains(point[None, :])[0])
        if inside:
            return False
        if clearance > 0.0:
            from trimesh.proximity import closest_point as _cp
            _, dists, _ = _cp(mesh_tm, point[None, :])
            return float(dists[0]) >= clearance
        return True
    except Exception as exc:
        log.debug("is_point_outside_mesh exception (treating as invalid): %s", exc)
        return False


def _batch_inside(points: np.ndarray, mesh_tm) -> np.ndarray:
    """
    Return bool array (N,) — True where point is inside the mesh.
    On failure returns all-True (conservative: mark all as invalid).
    """
    try:
        return mesh_tm.contains(points)
    except Exception as exc:
        log.debug("_batch_inside exception: %s", exc)
        return np.ones(len(points), dtype=bool)


def _batch_clearance(points: np.ndarray, mesh_tm) -> np.ndarray:
    """
    Return float array (N,) of distance-to-nearest-surface per point.
    On failure returns zeros (conservative: clearance = 0).
    """
    try:
        from trimesh.proximity import closest_point as _cp
        _, dists, _ = _cp(mesh_tm, points)
        return np.asarray(dists, dtype=float)
    except Exception as exc:
        log.debug("_batch_clearance exception: %s", exc)
        return np.zeros(len(points), dtype=float)


# ── Segment-level validation ──────────────────────────────────────────────────

class _FailReason:
    INTERSECTION = "colliding"
    INTERNAL     = "internal"
    TOO_CLOSE    = "too_close"
    OK           = "valid"


def _validate_segment_detail(
    pa:        np.ndarray,
    pb:        np.ndarray,
    bvh:       BVH,
    mesh_tm,
    clearance: float,
    n_samples: int,
) -> str:
    """
    Returns _FailReason string — the first rule that is violated, or "valid".
    """
    d      = pb - pa
    length = float(np.linalg.norm(d))
    if length < 1e-6:
        return _FailReason.OK   # degenerate — nothing to check

    direction = d / length

    # ── Rule 1: Full ray cast (ZERO endpoint skip) ────────────────────────────
    # We intentionally do NOT use margin / _HIT_EPSILON here.
    # Any mesh hit anywhere along the segment → reject.
    hit = bvh.ray_cast(pa, direction, max_dist=length)
    if hit is not None:
        return _FailReason.INTERSECTION

    # ── Prepare sample points ─────────────────────────────────────────────────
    # Exclude the exact endpoints (they sit on the surface by design).
    # Use a tiny inset (0.1 mm) so the contact point itself doesn't trigger.
    inset   = min(0.1, length * 0.05)
    t_start = inset / length
    t_end   = 1.0 - inset / length
    if t_start >= t_end:
        return _FailReason.OK

    ts     = np.linspace(t_start, t_end, n_samples)
    points = pa[None, :] + ts[:, None] * d[None, :]   # (N, 3)

    # ── Rule 2: Inside-mesh check ─────────────────────────────────────────────
    inside = _batch_inside(points, mesh_tm)
    if np.any(inside):
        return _FailReason.INTERNAL

    # ── Rule 3: Clearance check ───────────────────────────────────────────────
    dists = _batch_clearance(points, mesh_tm)
    if np.any(dists < clearance):
        return _FailReason.TOO_CLOSE

    return _FailReason.OK


def validate_segment_strict(
    pa:        np.ndarray,
    pb:        np.ndarray,
    bvh:       BVH,
    mesh_tm,
    clearance: float = DEFAULT_CLEARANCE_MM,
    n_samples: int   = DEFAULT_N_SAMPLES,
) -> bool:
    """
    Return True only if the segment is completely clean.

    This is the public boolean interface used by the pipeline.
    """
    reason = _validate_segment_detail(pa, pb, bvh, mesh_tm, clearance, n_samples)
    return reason == _FailReason.OK


# ── Batch filter ──────────────────────────────────────────────────────────────

def filter_valid_segments(
    segments:  List[SupportSegment],
    nodes:     List[SupportNode],
    bvh:       BVH,
    mesh_tm,
    clearance: float = DEFAULT_CLEARANCE_MM,
    n_samples: int   = DEFAULT_N_SAMPLES,
) -> Tuple[List[SupportNode], List[SupportSegment]]:
    """
    Hard-reject every segment that violates any validation rule.

    Returns (surviving_nodes, surviving_segments).

    Nodes that become completely disconnected after filtering are removed
    UNLESS they are tip or contact nodes (kept for debug visibility).
    """
    node_map: Dict[int, SupportNode] = {n.id: n for n in nodes}

    valid_segs: List[SupportSegment] = []
    n_rejected = 0
    reason_counts: Dict[str, int] = {}

    for seg in segments:
        a = node_map.get(seg.start_node_id)
        b = node_map.get(seg.end_node_id)
        if not a or not b:
            n_rejected += 1
            continue

        pa = np.array([a.position.x, a.position.y, a.position.z], dtype=float)
        pb = np.array([b.position.x, b.position.y, b.position.z], dtype=float)

        reason = _validate_segment_detail(pa, pb, bvh, mesh_tm, clearance, n_samples)
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

        if reason == _FailReason.OK:
            valid_segs.append(seg)
        else:
            n_rejected += 1
            log.debug(
                "Validator REJECT seg %d (%s→%s) @ (%.1f,%.1f,%.1f)→"
                "(%.1f,%.1f,%.1f): %s",
                seg.id,
                a.node_type, b.node_type,
                pa[0], pa[1], pa[2],
                pb[0], pb[1], pb[2],
                reason,
            )

    if n_rejected:
        log.info(
            "Validator: rejected %d/%d segments — %s",
            n_rejected, len(segments),
            ", ".join(f"{k}={v}" for k, v in reason_counts.items() if k != _FailReason.OK),
        )

    # ── Prune disconnected nodes ──────────────────────────────────────────────
    connected: Set[int] = set()
    for seg in valid_segs:
        connected.add(seg.start_node_id)
        connected.add(seg.end_node_id)

    surviving_nodes = [
        n for n in nodes
        if n.id in connected
        # Always keep tip/contact even if their segment was rejected — frontend
        # can colour them RED so the user sees what was dropped.
        or n.node_type in ("tip", "contact")
    ]

    return surviving_nodes, valid_segs


# ── External-face filter ──────────────────────────────────────────────────────

def is_external_face(
    centroid:  np.ndarray,     # (3,) face centroid
    normal:    np.ndarray,     # (3,) outward face normal (unit)
    mesh_tm,
    probe_dist: float = 0.1,   # mm inward probe to detect internal faces
) -> bool:
    """
    Return True if the face is on the external surface of the mesh.

    Strategy: probe slightly INWARD (centroid - probe * normal).
    - External face: inward probe enters the mesh → contains = True → is_external = True
    - Internal cavity face: centroid is already inside; inward probe goes deeper → also True
      BUT outward probe (centroid + probe * normal) would be inside the mesh for a cavity face.

    We use the outward probe:
    - External face: outward probe exits the mesh → contains = False → external = True
    - Internal face: outward probe stays inside → contains = True → external = False
    """
    probe_out = centroid + normal * probe_dist
    try:
        inside = bool(mesh_tm.contains(probe_out[None, :])[0])
        return not inside   # external face → outward probe is outside mesh
    except Exception:
        return True   # can't determine → assume external (don't over-filter)


# ── Debug tagging ─────────────────────────────────────────────────────────────

def tag_debug(
    segments:  List[SupportSegment],
    nodes:     List[SupportNode],
    bvh:       BVH,
    mesh_tm,
    clearance: float = DEFAULT_CLEARANCE_MM,
    n_samples: int   = DEFAULT_N_SAMPLES,
) -> Dict[int, str]:
    """
    Return a dict mapping segment.id → debug colour tag:

      "valid"     — GREEN  : passes all checks
      "colliding" — ORANGE : ray-cast intersection detected
      "internal"  — RED    : sample point inside mesh
      "too_close" — YELLOW : clearance violated

    Use this in the frontend 3D preview to colour-code segments.
    """
    node_map = {n.id: n for n in nodes}
    result: Dict[int, str] = {}

    for seg in segments:
        a = node_map.get(seg.start_node_id)
        b = node_map.get(seg.end_node_id)
        if not a or not b:
            result[seg.id] = "colliding"
            continue

        pa = np.array([a.position.x, a.position.y, a.position.z], dtype=float)
        pb = np.array([b.position.x, b.position.y, b.position.z], dtype=float)

        reason = _validate_segment_detail(pa, pb, bvh, mesh_tm, clearance, n_samples)
        result[seg.id] = reason

    return result
