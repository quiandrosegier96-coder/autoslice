"""
AutoSlice — Tree Support Engine: Tree Path Planner

Builds a directed tree graph from overhang cluster tip positions to the build
plate using a bottom-up 3-level hierarchical merge strategy:

  Level 0  →  tip nodes (one per cluster, at tipPosition)
  Level 1  →  sub-branch merge (L1 radius, ~15 mm)
  Level 2  →  branch merge     (L2 radius, ~35 mm)
  Level 3  →  trunk merge      (L3 radius, ~70 mm)
  Root     →  build-plate projection of each trunk base

At each merge level:
  - Group nodes by XY proximity
  - Compute centroid XY of the group
  - Find merge height satisfying angle constraint for every member
  - Create a merge node, connect all members as children

After tree construction:
  - Apply tip splay (outward push for visual clarity and printability)
  - Assign radii (taper from tip to root)
  - Compute BFS depths

Uses scipy.spatial.KDTree when available, falls back to O(n²) brute force.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from .models import (
    EngineConfig, SupportCluster, SupportContact,
    SupportNode, SupportSegment, Vec3,
)

try:
    from scipy.spatial import KDTree as _KDTree
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

# ── Constants ─────────────────────────────────────────────────────────────────

_TAPER_PER_LEVEL = 0.74
_BRANCH_FRAC     = 0.55   # merge height at this fraction of [floor..minTip]
_MIN_SEG_MM      = 1.5    # reject degenerate segments

_ID_COUNTER = 0


def _reset_ids() -> None:
    global _ID_COUNTER
    _ID_COUNTER = 0


def _new_id() -> int:
    global _ID_COUNTER
    i = _ID_COUNTER
    _ID_COUNTER += 1
    return i


# ── Public entry point ────────────────────────────────────────────────────────

def plan_tree(
    clusters: List[SupportCluster],
    config:   EngineConfig,
    floor_z:  float,
) -> Tuple[List[SupportNode], List[SupportSegment], List[SupportContact]]:
    """
    Build the full tree support graph.

    Returns (nodes, segments, contacts).
    """
    _reset_ids()

    if not clusters:
        return [], [], []

    nodes:    List[SupportNode]    = []
    segments: List[SupportSegment] = []
    contacts: List[SupportContact] = []

    tan_max = math.tan(math.radians(config.branch_angle_deg))

    # ── Step 1: Create tip + contact nodes ────────────────────────────────────
    tip_nodes: List[SupportNode] = []

    for cl in clusters:
        tip_pos = _splay_position(Vec3(0, 0, 0), cl.tip_position, config, initial=True)

        tip = SupportNode(
            id         = _new_id(),
            position   = cl.tip_position,
            radius     = config.tip_radius_mm,
            parent_id  = None,
            node_type  = "tip",
            cluster_id = cl.id,
        )
        nodes.append(tip)
        tip_nodes.append(tip)

        # Offset contact point away from the mesh surface along the average
        # cluster normal by z_distance_mm.  This ensures the contact node
        # is NOT on the surface (which would cause the segment endpoint to
        # sit inside or exactly on the mesh — a guaranteed clearance failure).
        import math as _math
        n_avg = cl.avg_normal                          # Vec3 (unit outward normal)
        contact_pos = Vec3(
            cl.centroid.x + n_avg.x * config.z_distance_mm,
            cl.centroid.y + n_avg.y * config.z_distance_mm,
            cl.centroid.z + n_avg.z * config.z_distance_mm,
        )
        contact = SupportNode(
            id         = _new_id(),
            position   = contact_pos,
            radius     = config.contact_radius_mm,
            parent_id  = tip.id,
            node_type  = "contact",
            cluster_id = cl.id,
        )
        nodes.append(contact)
        tip.child_ids.append(contact.id)

        contacts.append(SupportContact(
            id         = _new_id(),
            cluster_id = cl.id,
            node_id    = contact.id,
            position   = contact.position,
            radius     = config.contact_radius_mm,
            normal     = cl.avg_normal,
        ))

    # ── Step 2: Three-level hierarchical merge ────────────────────────────────
    current_level = tip_nodes

    for level, radius in enumerate([
        config.merge_l1_mm,
        config.merge_l2_mm,
        config.merge_l3_mm,
    ]):
        if len(current_level) <= 1:
            break
        groups = _group_by_xy(current_level, radius)
        next_level: List[SupportNode] = []

        for group in groups:
            if len(group) == 1:
                next_level.extend(group)
                continue

            merge = _create_merge_node(group, config, floor_z, tan_max,
                                       level=level, nodes=nodes)
            nodes.append(merge)
            next_level.append(merge)

        current_level = next_level

    # ── Step 3: Root nodes on build plate ─────────────────────────────────────
    trunk_nodes = current_level
    root_nodes: List[SupportNode] = []

    for trunk in trunk_nodes:
        n_desc  = _count_descendants(trunk, {n.id: n for n in nodes})
        r_trunk = min(
            config.trunk_radius_min_mm + math.sqrt(max(n_desc, 1)) * 0.52,
            config.trunk_radius_max_mm,
        )

        root = SupportNode(
            id        = _new_id(),
            position  = Vec3(trunk.position.x, trunk.position.y, floor_z),
            radius    = r_trunk * 1.15,
            parent_id = None,
            node_type = "root",
        )
        nodes.append(root)
        root_nodes.append(root)

        trunk.parent_id = root.id
        root.child_ids.append(trunk.id)

        # Upgrade trunk type
        trunk.node_type = "trunk"
        trunk.radius    = r_trunk

    # ── Step 4: Assign radii (taper root→tip) ─────────────────────────────────
    node_map = {n.id: n for n in nodes}
    _assign_depths(root_nodes, node_map)
    _assign_radii(nodes, config)

    # ── Step 5: Build segment list ────────────────────────────────────────────
    seg_id = 0
    for node in nodes:
        if node.parent_id is None:
            continue
        parent = node_map.get(node.parent_id)
        if parent is None:
            continue
        length = parent.position.dist(node.position)
        if length < _MIN_SEG_MM:
            continue
        segments.append(SupportSegment(
            id            = seg_id,
            start_node_id = parent.id,
            end_node_id   = node.id,
            radius_start  = parent.radius,
            radius_end    = node.radius,
            length        = length,
            is_trunk      = parent.node_type in ("root", "trunk"),
        ))
        seg_id += 1

    return nodes, segments, contacts


# ── Merge node creation ────────────────────────────────────────────────────────

def _create_merge_node(
    group:   List[SupportNode],
    config:  EngineConfig,
    floor_z: float,
    tan_max: float,
    level:   int,
    nodes:   List[SupportNode],
) -> SupportNode:
    """
    Place a merge node that satisfies the branch-angle constraint for all
    members of `group`, then connect each member as a child.
    """
    # XY centroid of the group
    cx = sum(n.position.x for n in group) / len(group)
    cy = sum(n.position.y for n in group) / len(group)

    # Initial merge height: BRANCH_FRAC of [floor..minZ]
    min_z    = min(n.position.z for n in group)
    merge_z  = floor_z + (min_z - floor_z) * _BRANCH_FRAC

    # Enforce angle constraint for every child
    if tan_max > 1e-9:
        for n in group:
            d_xy = math.sqrt((n.position.x - cx) ** 2 + (n.position.y - cy) ** 2)
            if d_xy > 1e-6:
                max_z   = n.position.z - d_xy / tan_max
                merge_z = min(merge_z, max_z)

    # Safety clamps
    merge_z = max(merge_z, floor_z + 2.0)
    merge_z = min(merge_z, max(min_z - 0.5, floor_z + 1.0))

    # Node type
    ntype = ["branch", "branch", "trunk"][min(level, 2)]

    merge = SupportNode(
        id        = _new_id(),
        position  = Vec3(cx, cy, merge_z),
        radius    = config.branch_radius_mm,
        parent_id = None,
        node_type = ntype,
    )

    # Splay children from this merge point
    for n in group:
        sp = _splay_position(merge.position, n.position, config)
        n.position = sp
        n.parent_id = merge.id
        merge.child_ids.append(n.id)

    return merge


# ── Splay (outward lean) ───────────────────────────────────────────────────────

def _splay_position(
    parent: Vec3,
    tip:    Vec3,
    config: EngineConfig,
    initial: bool = False,
) -> Vec3:
    """
    Push `tip` outward from `parent` so that the branch has a visible lean.
    Preserves tip.z.
    """
    dx = tip.x - parent.x
    dy = tip.y - parent.y
    d  = math.sqrt(dx * dx + dy * dy)

    min_spread = config.min_xz_spread_mm

    if d < 1e-6:
        ndx, ndy = min_spread, 0.0
    elif d < min_spread:
        s   = min_spread / d
        ndx = dx * s
        ndy = dy * s
    else:
        ndx = dx * config.splay_mult
        ndy = dy * config.splay_mult

    return Vec3(parent.x + ndx, parent.y + ndy, tip.z)


# ── Proximity grouping ────────────────────────────────────────────────────────

def _group_by_xy(
    nodes:  List[SupportNode],
    radius: float,
) -> List[List[SupportNode]]:
    """Group nodes whose XY positions are within `radius` of each other."""
    if not nodes:
        return []

    if _HAS_SCIPY and len(nodes) > 10:
        import numpy as np
        pts  = np.array([[n.position.x, n.position.y] for n in nodes])
        tree = _KDTree(pts)
        used = [False] * len(nodes)
        groups: List[List[SupportNode]] = []
        for i in range(len(nodes)):
            if used[i]:
                continue
            idxs = tree.query_ball_point(pts[i], radius)
            grp  = [nodes[j] for j in idxs if not used[j]]
            for j in idxs:
                used[j] = True
            groups.append(grp)
        return groups

    # Brute force O(n²) fallback
    used   = [False] * len(nodes)
    groups = []
    for i, ni in enumerate(nodes):
        if used[i]:
            continue
        grp  = [ni]
        used[i] = True
        for j in range(i + 1, len(nodes)):
            if used[j]:
                continue
            if ni.position.xy_dist(nodes[j].position) <= radius:
                grp.append(nodes[j])
                used[j] = True
        groups.append(grp)
    return groups


# ── Radius / depth assignment ─────────────────────────────────────────────────

def _assign_depths(
    roots:    List[SupportNode],
    node_map: Dict[int, SupportNode],
    depth:    int = 0,
) -> None:
    """BFS depth assignment from root nodes."""
    queue = [(r, 0) for r in roots]
    while queue:
        node, d = queue.pop(0)
        node.depth = d
        for cid in node.child_ids:
            child = node_map.get(cid)
            if child:
                queue.append((child, d + 1))


def _assign_radii(
    nodes:  List[SupportNode],
    config: EngineConfig,
) -> None:
    """
    Assign radii based on depth.
    Root / trunk: trunk_radius (sized by descendant count — pre-assigned).
    Branch: branch_radius * TAPER^(depth - trunk_depth).
    Tip / contact: tip_radius.
    """
    for n in nodes:
        if n.node_type in ("root", "trunk"):
            pass  # already assigned in plan_tree
        elif n.node_type in ("tip",):
            n.radius = config.tip_radius_mm
        elif n.node_type == "contact":
            n.radius = config.contact_radius_mm
        else:
            # branch / waypoint: taper from branch_radius by depth
            depth_from_trunk = max(0, n.depth - 2)
            n.radius = max(
                config.branch_radius_mm * (_TAPER_PER_LEVEL ** depth_from_trunk),
                config.contact_radius_mm,
            )


def _count_descendants(root: SupportNode, node_map: Dict[int, SupportNode]) -> int:
    """BFS count of all descendant nodes."""
    count = 0
    queue = list(root.child_ids)
    while queue:
        nid  = queue.pop()
        node = node_map.get(nid)
        if node:
            count += 1
            queue.extend(node.child_ids)
    return count
