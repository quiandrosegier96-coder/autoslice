"""
AutoSlice — Tree Support Engine: Graph Optimizer

Post-processing passes applied after tree construction and collision avoidance:

  Pass 1 — Minimum feature enforcement
    Remove segments that are thinner than the nozzle diameter or too short
    to print. Merge the thinner child into its parent (inherit parent position).

  Pass 2 — Redundant node pruning
    Remove "pass-through" nodes: nodes with exactly one parent and one child
    where the three positions are nearly collinear (angle deviation < 5°).
    The intermediate node adds no branch structure.

  Pass 3 — Long-span stabilisation
    For trunk segments longer than MAX_TRUNK_MM, insert a mid-reinforcement
    node with an increased radius to prevent sway during printing.

  Pass 4 — Contact zone radius adjustment
    Ensure all contact-zone radii are ≥ nozzle_diameter (printable).

  Pass 5 — Structural validation
    Report warnings for branches that are:
      - Too horizontal (angle from vertical > branch_angle_deg + 10°)
      - Too long without support (> MAX_UNSUPPORTED_MM)
      - Radius below minimum printable size
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

from .models import EngineConfig, SupportNode, SupportSegment

_MAX_TRUNK_MM        = 80.0   # insert mid-node above this length
_MAX_UNSUPPORTED_MM  = 120.0  # warn if a branch is longer
_COLLINEAR_DEG       = 5.0    # prune if deviation from straight is less than this

_REINFORCE_ID_BASE   = 50_000


def optimize(
    nodes:    List[SupportNode],
    segments: List[SupportSegment],
    config:   EngineConfig,
    warnings: List[str],
) -> Tuple[List[SupportNode], List[SupportSegment]]:
    """
    Run all optimisation passes in order.
    Mutates lists in-place and returns them.
    """
    node_map = {n.id: n for n in nodes}

    _pass_feature_enforcement(nodes, segments, node_map, config, warnings)
    _pass_prune_collinear(nodes, segments, node_map, config)
    _pass_long_trunk_reinforce(nodes, segments, node_map, config)
    _pass_contact_radius(nodes, config)
    _pass_structural_validation(nodes, segments, node_map, config, warnings)

    # Rebuild clean lists (remove None placeholders if any)
    nodes    = [n for n in nodes    if n is not None]
    segments = [s for s in segments if s is not None]

    return nodes, segments


# ── Pass 1: Minimum feature size ──────────────────────────────────────────────

def _pass_feature_enforcement(
    nodes:    List[SupportNode],
    segments: List[SupportSegment],
    node_map: Dict[int, SupportNode],
    config:   EngineConfig,
    warnings: List[str],
) -> None:
    min_r = config.nozzle_diameter_mm * 0.5   # minimum meaningful radius

    to_remove_segs = []
    for i, seg in enumerate(segments):
        remove = False

        if seg.length < config.min_segment_mm:
            remove = True

        if seg.radius_end < min_r:
            warnings.append(
                f"Segment {seg.id}: tip radius {seg.radius_end:.2f} mm < "
                f"nozzle diameter {config.nozzle_diameter_mm:.2f} mm — "
                "increasing to minimum."
            )
            seg.radius_end = min_r

        if remove:
            to_remove_segs.append(i)

    for i in reversed(to_remove_segs):
        segments.pop(i)


# ── Pass 2: Collinear node pruning ────────────────────────────────────────────

def _pass_prune_collinear(
    nodes:    List[SupportNode],
    segments: List[SupportSegment],
    node_map: Dict[int, SupportNode],
    config:   EngineConfig,
) -> None:
    cos_thresh = math.cos(math.radians(180.0 - _COLLINEAR_DEG))

    pruned_ids = set()

    for node in list(nodes):
        if node.node_type not in ("branch", "waypoint"):
            continue
        if node.parent_id is None or len(node.child_ids) != 1:
            continue

        parent = node_map.get(node.parent_id)
        child  = node_map.get(node.child_ids[0])
        if not parent or not child:
            continue

        # Vector parent→node and node→child
        pn = node.position - parent.position
        nc = child.position - node.position

        pn_len = pn.length()
        nc_len = nc.length()
        if pn_len < 1e-6 or nc_len < 1e-6:
            continue

        dot = (pn * (1.0 / pn_len)).dot(nc * (1.0 / nc_len))
        if dot > cos_thresh:   # nearly collinear
            # Bypass: parent → child directly
            child.parent_id = parent.id
            if node.id in parent.child_ids:
                parent.child_ids.remove(node.id)
            if node.child_ids[0] not in parent.child_ids:
                parent.child_ids.append(node.child_ids[0])
            pruned_ids.add(node.id)

            # Replace the two segments with one combined segment
            _merge_segments_through_node(segments, node, parent, child, node_map)

    # Remove pruned nodes
    nodes[:] = [n for n in nodes if n.id not in pruned_ids]


def _merge_segments_through_node(
    segments: List[SupportSegment],
    node:     SupportNode,
    parent:   SupportNode,
    child:    SupportNode,
    node_map: Dict[int, SupportNode],
) -> None:
    """Replace two segments p→n and n→c with one p→c."""
    seg_pn = seg_nc = None
    for seg in segments:
        if seg.start_node_id == parent.id and seg.end_node_id == node.id:
            seg_pn = seg
        if seg.start_node_id == node.id and seg.end_node_id == child.id:
            seg_nc = seg

    if not seg_pn or not seg_nc:
        return

    seg_pn.end_node_id  = child.id
    seg_pn.radius_end   = seg_nc.radius_end
    seg_pn.length      += seg_nc.length

    try:
        segments.remove(seg_nc)
    except ValueError:
        pass


# ── Pass 3: Long-span trunk reinforcement ────────────────────────────────────

_reinforce_counter = _REINFORCE_ID_BASE


def _pass_long_trunk_reinforce(
    nodes:    List[SupportNode],
    segments: List[SupportSegment],
    node_map: Dict[int, SupportNode],
    config:   EngineConfig,
) -> None:
    global _reinforce_counter

    new_nodes = []
    new_segs  = []

    for seg in list(segments):
        if not seg.is_trunk or seg.length <= _MAX_TRUNK_MM:
            continue

        a = node_map.get(seg.start_node_id)
        b = node_map.get(seg.end_node_id)
        if not a or not b:
            continue

        mid_pos  = a.position.lerp(b.position, 0.5)
        mid_r    = max(seg.radius_start, seg.radius_end) * 1.10   # slight reinforcement

        mid = SupportNode(
            id        = _reinforce_counter,
            position  = mid_pos,
            radius    = mid_r,
            parent_id = a.id,
            node_type = "trunk",
        )
        mid.child_ids = [b.id]
        _reinforce_counter += 1

        node_map[mid.id] = mid
        new_nodes.append(mid)

        # Replace segment with two half-segments
        seg_a = SupportSegment(
            id            = seg.id,
            start_node_id = a.id,
            end_node_id   = mid.id,
            radius_start  = seg.radius_start,
            radius_end    = mid_r,
            length        = seg.length * 0.5,
            is_trunk      = True,
        )
        seg_b = SupportSegment(
            id            = _reinforce_counter,
            start_node_id = mid.id,
            end_node_id   = b.id,
            radius_start  = mid_r,
            radius_end    = seg.radius_end,
            length        = seg.length * 0.5,
            is_trunk      = True,
        )
        _reinforce_counter += 1

        idx = segments.index(seg)
        segments[idx:idx + 1] = [seg_a, seg_b]

        # Fix adjacency
        if b.id in a.child_ids:
            a.child_ids.remove(b.id)
        a.child_ids.append(mid.id)
        b.parent_id = mid.id

        new_segs.append(seg_b)

    nodes.extend(new_nodes)


# ── Pass 4: Contact radius ────────────────────────────────────────────────────

def _pass_contact_radius(
    nodes:  List[SupportNode],
    config: EngineConfig,
) -> None:
    min_r = config.nozzle_diameter_mm
    for n in nodes:
        if n.node_type == "contact":
            n.radius = max(n.radius, min_r)


# ── Pass 5: Structural validation ────────────────────────────────────────────

def _pass_structural_validation(
    nodes:    List[SupportNode],
    segments: List[SupportSegment],
    node_map: Dict[int, SupportNode],
    config:   EngineConfig,
    warnings: List[str],
) -> None:
    max_angle = config.branch_angle_deg + 10.0
    cos_max   = math.cos(math.radians(max_angle))

    for seg in segments:
        a = node_map.get(seg.start_node_id)
        b = node_map.get(seg.end_node_id)
        if not a or not b:
            continue

        # Angle from vertical
        dz    = abs(b.position.z - a.position.z)
        d_xy  = a.position.xy_dist(b.position)
        if seg.length > 1e-6:
            cos_from_vert = dz / seg.length
        else:
            cos_from_vert = 1.0

        if cos_from_vert < cos_max:
            warnings.append(
                f"Segment {seg.id} ({a.node_type}→{b.node_type}) exceeds "
                f"max angle: {math.degrees(math.acos(cos_from_vert)):.1f}°"
            )

        if seg.length > _MAX_UNSUPPORTED_MM and not seg.is_trunk:
            warnings.append(
                f"Segment {seg.id} length {seg.length:.1f} mm may be unstable "
                "without intermediate support."
            )

        if seg.radius_end < config.nozzle_diameter_mm * 0.5:
            warnings.append(
                f"Segment {seg.id} tip radius {seg.radius_end:.2f} mm is below "
                "minimum printable size."
            )
