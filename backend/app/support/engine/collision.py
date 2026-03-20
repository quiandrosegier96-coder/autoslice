"""
AutoSlice — Tree Support Engine: Collision Avoidance

For each support segment (parent → child), cast a ray along the segment.
If the ray hits the mesh within the segment's length:
  - Compute a waypoint pushed outward from the mesh bounding-box centre
  - Insert the waypoint node between parent and child
  - Update adjacency in the node graph

Repeats up to MAX_ITER times per segment to handle concave geometry.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

import numpy as np

from .bvh import BVH
from .models import EngineConfig, SupportNode, SupportSegment, Vec3

_MAX_ITER    = 4
_HIT_EPSILON = 0.4   # mm — ignore hits within this distance of the ray origin

_ID_COUNTER = 10_000  # start high to avoid collisions with planner IDs


def _new_id() -> int:
    global _ID_COUNTER
    _ID_COUNTER += 1
    return _ID_COUNTER


# ── Main entry point ──────────────────────────────────────────────────────────

def avoid_collisions(
    nodes:    List[SupportNode],
    segments: List[SupportSegment],
    bvh:      BVH,
    bbox_center: np.ndarray,        # mesh bounding-box centre for outward push
    config:   EngineConfig,
) -> Tuple[List[SupportNode], List[SupportSegment]]:
    """
    Mutate `nodes` and `segments` in-place (adding waypoints where needed).

    Returns updated (nodes, segments).
    """
    node_map: Dict[int, SupportNode] = {n.id: n for n in nodes}

    # Work on a snapshot so insertions don't affect iteration
    original_segs = list(segments)
    seg_id        = max((s.id for s in segments), default=0) + 1

    for seg in original_segs:
        seg_id = _process_segment(
            seg, node_map, segments, bvh, bbox_center, config, seg_id,
        )

    return list(node_map.values()), segments


def _process_segment(
    seg:        SupportSegment,
    node_map:   Dict[int, SupportNode],
    segments:   List[SupportSegment],
    bvh:        BVH,
    bbox_center: np.ndarray,
    config:     EngineConfig,
    next_seg_id: int,
) -> int:
    """Check and fix one segment. Returns updated next_seg_id."""
    margin = config.collision_margin_mm

    for _iter in range(_MAX_ITER):
        a = node_map.get(seg.start_node_id)
        b = node_map.get(seg.end_node_id)
        if not a or not b:
            return next_seg_id

        pa = np.array([a.position.x, a.position.y, a.position.z])
        pb = np.array([b.position.x, b.position.y, b.position.z])

        d   = pb - pa
        length = float(np.linalg.norm(d))
        if length < 1e-6:
            return next_seg_id
        direction = d / length

        # Offset origin to avoid self-intersection at the node sphere
        origin = pa + direction * _HIT_EPSILON
        eff_len = length - 2.0 * _HIT_EPSILON
        if eff_len <= 0.0:
            return next_seg_id

        hit = bvh.ray_cast(origin, direction, max_dist=eff_len - margin)
        if hit is None:
            return next_seg_id   # no collision — done

        hit_dist, _ = hit
        hit_point   = origin + direction * hit_dist

        # Outward direction from mesh centre (XY only for stability)
        out = np.array([
            hit_point[0] - bbox_center[0],
            hit_point[1] - bbox_center[1],
            0.0,
        ])
        out_norm = float(np.linalg.norm(out))
        if out_norm < 1e-6:
            out = np.array([1.0, 0.0, 0.0])
        else:
            out = out / out_norm

        push = config.collision_margin_mm * config.collision_waypoint_offset_mult

        # Waypoint: clamped to segment Z range
        wp_z = float(np.clip(
            hit_point[2],
            min(pa[2], pb[2]),
            max(pa[2], pb[2]),
        ))
        wp_pos = Vec3(
            float(hit_point[0]) + out[0] * push,
            float(hit_point[1]) + out[1] * push,
            wp_z,
        )

        # Create waypoint node
        rMid = (seg.radius_start + seg.radius_end) * 0.5
        wp   = SupportNode(
            id        = _new_id(),
            position  = wp_pos,
            radius    = rMid,
            parent_id = a.id,
            node_type = "waypoint",
        )
        node_map[wp.id] = wp

        # Update adjacency
        a.child_ids = [cid if cid != b.id else wp.id for cid in a.child_ids]
        wp.child_ids = [b.id]
        b.parent_id  = wp.id

        # Replace seg with two new segments
        try:
            idx = segments.index(seg)
        except ValueError:
            idx = -1

        seg_a = SupportSegment(
            id            = next_seg_id,
            start_node_id = a.id,
            end_node_id   = wp.id,
            radius_start  = seg.radius_start,
            radius_end    = rMid,
            length        = float(np.linalg.norm(
                np.array([wp_pos.x, wp_pos.y, wp_pos.z]) - pa)),
            is_trunk      = seg.is_trunk,
        )
        seg_b = SupportSegment(
            id            = next_seg_id + 1,
            start_node_id = wp.id,
            end_node_id   = b.id,
            radius_start  = rMid,
            radius_end    = seg.radius_end,
            length        = float(np.linalg.norm(
                pb - np.array([wp_pos.x, wp_pos.y, wp_pos.z]))),
            is_trunk      = False,
        )
        next_seg_id += 2

        if idx >= 0:
            segments[idx:idx + 1] = [seg_a, seg_b]
        else:
            segments.extend([seg_a, seg_b])

        # Continue checking seg_b
        seg = seg_b

    return next_seg_id
