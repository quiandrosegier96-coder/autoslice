"""
AutoSlice — Tree support skeleton generator.

Converts detected support columns into an organic tree-branch skeleton
that the 3D viewer can render as tapered, branching support structures.

Algorithm overview
──────────────────
1. Cluster support columns by XY proximity (greedy single-linkage).
2. For each cluster create one trunk root on the build plate whose XY
   position is the cluster centroid.
3. Grow the trunk upward to a "branching node" height (~60% of the way
   from z_min to the lowest overhang in the cluster).
4. Small clusters (≤ 3 tips): emit one branch per column directly from
   the branching node to the overhang contact point.
5. Large clusters: apply a second-level clustering, add intermediate
   sub-trunks, then emit individual tip branches.
6. Taper radii linearly from base (thick) to tip (thin).

Coordinate space
────────────────
All coordinates are in 3MF space (Z-up, mm).  The frontend applies the
same -π/2 X-rotation + center-subtraction used for every other support
object, so no special handling is needed here.
"""

from __future__ import annotations

import math
from app.support.models import SupportColumn, TreeBranch

# ── Tuneable constants ─────────────────────────────────────────────────────────

# Columns within this XY distance are placed on a shared trunk
_PRIMARY_CLUSTER_MM   = 18.0

# Tip branches from the same sub-cluster share an intermediate sub-trunk
_SECONDARY_CLUSTER_MM =  9.0

# Maximum trunk clusters before we start merging aggressively
_MAX_TRUNKS = 30

# Trunk radii (mm)
_TRUNK_BASE_MIN   = 2.2   # thinnest possible trunk base
_TRUNK_BASE_MAX   = 5.0   # thickest possible trunk base
_TRUNK_TAPER      = 0.60  # top radius = base * taper

# Sub-trunk and tip radii
_SUB_TRUNK_TAPER  = 0.78  # sub-trunk start = trunk_top * this
_SUB_TRUNK_END    = 0.52  # sub-trunk end   = sub_start * this
_TIP_RADIUS       = 0.55  # final contact-point radius (mm)

# The branching node is placed this fraction of the way from z_min to the
# lowest overhang z_bottom in the cluster.
_BRANCH_HEIGHT_FRACTION = 0.55

# Minimum height a trunk must reach (mm above z_min)
_MIN_TRUNK_HEIGHT_MM = 4.0

# Safety margin below overhang — branch end is this far below z_top
_BRANCH_END_MARGIN_MM = 0.0   # flush with overhang underside

# Minimum XY spread to guarantee visually angled branches.
# If a column is too close to its trunk centroid, the branch looks vertical.
# We push the branch tip slightly outward so all branches have a lean angle.
_MIN_XY_SPREAD_MM = 3.5

# Extra outward lean applied to tip position (multiplier on spread vector).
# Values > 1.0 exaggerate the splay for more organic appearance.
_BRANCH_SPLAY = 1.25


# ── Public entry point ─────────────────────────────────────────────────────────

def generate_tree_branches(
    columns: list[SupportColumn],
    z_min: float,
) -> list[TreeBranch]:
    """
    Build a tree-branch skeleton from a list of support columns.

    Parameters
    ----------
    columns : list[SupportColumn]
        Support columns produced by the overhang detector (3MF space, Z-up).
    z_min : float
        Minimum Z of the model — defines the build plate height.

    Returns
    -------
    list[TreeBranch]
        Ordered list of branch segments.  Each segment carries its parent_id
        so the frontend can reconstruct the full tree topology.
    """
    if not columns:
        return []

    branches: list[TreeBranch] = []
    next_id = 0

    primary_groups = _cluster(columns, _PRIMARY_CLUSTER_MM)

    # If we produced too many trunks, increase the merge distance adaptively
    if len(primary_groups) > _MAX_TRUNKS:
        scale = math.sqrt(len(primary_groups) / _MAX_TRUNKS)
        primary_groups = _cluster(columns, _PRIMARY_CLUSTER_MM * scale)

    for group in primary_groups:
        cx, cy = _centroid_xy(group)
        min_z_bottom = min(c.z_bottom for c in group)

        # Branching node height
        raw_branch_h = z_min + (min_z_bottom - z_min) * _BRANCH_HEIGHT_FRACTION
        branch_h = max(raw_branch_h, z_min + _MIN_TRUNK_HEIGHT_MM)
        branch_h = min(branch_h, min_z_bottom - 0.5)   # must be below overhang

        n = len(group)
        trunk_r_base = min(_TRUNK_BASE_MIN + n * 0.45, _TRUNK_BASE_MAX)
        trunk_r_top  = trunk_r_base * _TRUNK_TAPER

        # ── Trunk (build plate → branching node) ──────────────────────────────
        trunk_id = next_id
        branches.append(TreeBranch(
            id=next_id, parent_id=None,
            start_x=cx, start_y=cy, start_z=z_min,
            end_x=cx,   end_y=cy,   end_z=branch_h,
            start_radius=trunk_r_base,
            end_radius=trunk_r_top,
            is_tip=False,
        ))
        next_id += 1

        if n <= 3:
            # ── Direct branches from branching node to each tip ────────────────
            for col in group:
                ex, ey = _splayed_tip(cx, cy, col.x, col.y)
                branches.append(TreeBranch(
                    id=next_id, parent_id=trunk_id,
                    start_x=cx,  start_y=cy,  start_z=branch_h,
                    end_x=ex,    end_y=ey,    end_z=col.z_top - _BRANCH_END_MARGIN_MM,
                    start_radius=trunk_r_top,
                    end_radius=_TIP_RADIUS,
                    is_tip=True,
                ))
                next_id += 1

        else:
            # ── Two-level hierarchy: sub-trunks → tips ────────────────────────
            sub_groups = _cluster(group, _SECONDARY_CLUSTER_MM)

            for sub in sub_groups:
                sub_cx, sub_cy = _centroid_xy(sub)
                sub_min_zb = min(c.z_bottom for c in sub)

                # Sub-branching node: halfway between trunk top and sub_min_zb
                raw_sub_h = branch_h + (sub_min_zb - branch_h) * 0.55
                sub_branch_h = max(raw_sub_h, branch_h + 0.5)
                sub_branch_h = min(sub_branch_h, sub_min_zb - 0.5)

                sub_r_start = trunk_r_top  * _SUB_TRUNK_TAPER
                sub_r_end   = sub_r_start  * _SUB_TRUNK_END

                # Ensure sub-trunk endpoint is visibly splayed from trunk tip
                scx, scy = _splayed_tip(cx, cy, sub_cx, sub_cy)

                # Sub-trunk
                sub_trunk_id = next_id
                branches.append(TreeBranch(
                    id=next_id, parent_id=trunk_id,
                    start_x=cx,   start_y=cy,   start_z=branch_h,
                    end_x=scx,    end_y=scy,    end_z=sub_branch_h,
                    start_radius=sub_r_start,
                    end_radius=sub_r_end,
                    is_tip=False,
                ))
                next_id += 1

                # Tip branches from sub-trunk tip to each column
                for col in sub:
                    ex, ey = _splayed_tip(scx, scy, col.x, col.y)
                    branches.append(TreeBranch(
                        id=next_id, parent_id=sub_trunk_id,
                        start_x=scx,  start_y=scy,  start_z=sub_branch_h,
                        end_x=ex,     end_y=ey,     end_z=col.z_top - _BRANCH_END_MARGIN_MM,
                        start_radius=sub_r_end,
                        end_radius=_TIP_RADIUS,
                        is_tip=True,
                    ))
                    next_id += 1

    return branches


# ── Helpers ────────────────────────────────────────────────────────────────────

def _cluster(
    columns: list[SupportColumn],
    max_dist: float,
) -> list[list[SupportColumn]]:
    """
    Greedy single-linkage clustering by XY Euclidean distance.

    Each column is assigned to the first cluster whose seed is within
    max_dist.  This is O(n²) but n is capped at MAX_COLUMNS (300) in the
    caller, so it is fast enough for interactive use.
    """
    used  = [False] * len(columns)
    groups: list[list[SupportColumn]] = []

    for i, col in enumerate(columns):
        if used[i]:
            continue
        group = [col]
        used[i] = True
        for j in range(i + 1, len(columns)):
            if used[j]:
                continue
            if math.hypot(col.x - columns[j].x, col.y - columns[j].y) <= max_dist:
                group.append(columns[j])
                used[j] = True
        groups.append(group)

    return groups


def _centroid_xy(cols: list[SupportColumn]) -> tuple[float, float]:
    n = len(cols)
    return sum(c.x for c in cols) / n, sum(c.y for c in cols) / n


def _splayed_tip(
    origin_x: float, origin_y: float,
    target_x: float, target_y: float,
) -> tuple[float, float]:
    """
    Return the effective XY endpoint for a branch tip.

    Ensures the branch has a minimum visible lean (_MIN_XY_SPREAD_MM).
    Also applies _BRANCH_SPLAY to exaggerate the spread for a more
    organic, tree-like appearance.
    """
    dx = target_x - origin_x
    dy = target_y - origin_y
    dist = math.hypot(dx, dy)

    if dist < _MIN_XY_SPREAD_MM:
        # Direction is almost vertical — push target outward to min spread
        if dist < 1e-6:
            # Degenerate case: branch directly above trunk — pick +X direction
            dx, dy = _MIN_XY_SPREAD_MM, 0.0
        else:
            scale = _MIN_XY_SPREAD_MM / dist
            dx *= scale
            dy *= scale
    else:
        dx *= _BRANCH_SPLAY
        dy *= _BRANCH_SPLAY

    return origin_x + dx, origin_y + dy
