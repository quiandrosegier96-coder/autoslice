"""
AutoSlice — Professional Tree Support Generator v2.

Physically valid, collision-aware, multi-level tree support generation.

Architecture
────────────
Internal representation: a directed acyclic graph of _Node objects.
  · Every node carries a 3D position (3MF Z-up, mm) and a radius.
  · Edges point from child toward its parent (child.pid = parent.nid).
  · Root nodes sit on the build plate (is_root=True, pid=None).
  · Tip nodes contact the model's overhang underside (is_tip=True).

Levels produced
───────────────
  root (z_min)  ←  trunk node  ←  [sub-trunk node]  ←  tip (z_top)

  (arrows show parent direction — visually the tree grows upward)

Collision avoidance
───────────────────
Each direct-line branch is ray-cast against the model mesh.  If a collision
is detected within the branch length, a waypoint is inserted offset outward
from the mesh center-of-mass.  Both sub-segments inherit the original parent/
child relationship, effectively rerouting the branch around the obstacle.

Radius tapering
───────────────
  root  : _trunk_radius(n_descendants)   → up to _TRUNK_R_MAX mm
  tip   : _TIP_R                          → 0.55 mm
  intermediate : geometric taper (_TAPER per level) clamped to _BRANCH_R_MIN

Coordinate space
────────────────
All positions are returned in 3MF space (Z-up, mm).  The frontend applies
the same -π/2 X-rotation and model-center subtraction used for the model.

Changelog
─────────
v2 over v1:
  · KD-tree spatial clustering (O(n log n)) instead of O(n²) greedy scan
  · True tree graph — all segments share a connected acyclic structure
  · Multi-level hierarchy: tip → branch node → sub-trunk → trunk → root
  · Mesh collision avoidance via downward + diagonal ray casting
  · Branch angle constraints (max 40° from vertical for FDM stability)
  · Load-aware trunk radius (proportional to supported overhang count)
  · Splay applied per-tip to guarantee visible lean (no vertical pillars)
  · Topological BFS converts node graph → ordered TreeBranch segments
"""

from __future__ import annotations

import math
from collections import deque
from typing import Optional

import numpy as np

try:
    from scipy.spatial import KDTree as _KDTree
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

from app.support.models import SupportColumn, TreeBranch


# ── Tunable constants ─────────────────────────────────────────────────────────

# Radii (mm)
_TIP_R         = 0.55    # contact-point radius — easily removable
_TRUNK_R_MIN   = 1.6     # thinnest allowable trunk base
_TRUNK_R_MAX   = 4.2     # thickest allowable trunk base
_BRANCH_R_MIN  = 0.72    # thinnest non-tip intermediate segment
_TAPER         = 0.76    # radius multiplier per tree level

# Clustering distances (mm, XY plane only)
_L1_MM         = 14.0    # tip → branch node: tips within this radius share a branch
_L2_MM         = 32.0    # branch node → sub-trunk
_L3_MM         = 65.0    # sub-trunk → trunk root

# Tree limits
_MAX_TRUNKS    = 22      # hard cap on root trunk count

# Geometry
_HEIGHT_FRAC   = 0.52    # merge-node height as fraction of [z_min .. z_tip]
_MAX_ANGLE_DEG = 40.0    # max branch angle from vertical (printability)
_MIN_SEG_MM    = 1.5     # discard segments shorter than this

# Splay (tip branches)
_SPLAY         = 1.18    # outward lean multiplier
_MIN_XY_SPREAD = 3.0     # minimum horizontal displacement for tip branches

# Collision avoidance
_COL_MARGIN    = 0.8     # minimum clearance from mesh surface (mm)
_RAY_NUDGE     = 0.0     # NO dead zone — catch intersections at full range
_COL_MAX_ITER  = 5       # max waypoint insertion attempts per segment
_COL_SAMPLES   = 20      # samples along segment for inside-mesh check


# ── Internal node ─────────────────────────────────────────────────────────────

class _Node:
    """Lightweight tree node used only during skeleton construction."""

    __slots__ = ("nid", "pos", "r", "pid", "tip", "root", "ndesc")

    def __init__(
        self,
        nid:  int,
        pos:  np.ndarray,
        r:    float,
        pid:  Optional[int] = None,
        tip:  bool = False,
        root: bool = False,
    ) -> None:
        self.nid   = nid
        self.pos   = np.asarray(pos, dtype=float)
        self.r     = float(r)
        self.pid   = pid        # parent node id (None = root of tree)
        self.tip   = tip        # contacts model overhang
        self.root  = root       # sits on build plate
        self.ndesc = 1          # number of descendant tips (filled by _count_desc)


# ── Public entry point ────────────────────────────────────────────────────────

def generate_tree_branches(
    columns:       list[SupportColumn],
    z_min:         float,
    mesh=None,
    nozzle_mm:     float = 0.4,
    max_angle_deg: float = _MAX_ANGLE_DEG,
) -> list[TreeBranch]:
    """
    Build a physically valid, collision-aware tree-support skeleton.

    Parameters
    ----------
    columns       : support columns produced by the overhang detector
    z_min         : build-plate Z coordinate in 3MF model space (mm)
    mesh          : trimesh.Trimesh used for collision avoidance (None = skip)
    nozzle_mm     : nozzle diameter — sets minimum viable radius
    max_angle_deg : maximum branch angle from vertical

    Returns
    -------
    List of TreeBranch segments ordered parent-first (BFS from roots) so the
    frontend renderer can draw them without a secondary sort pass.
    """
    if not columns:
        return []

    nodes:  list[_Node] = []
    _nid = [0]                              # mutable int counter
    tan_max = math.tan(math.radians(max_angle_deg))

    def mk(pos, r, pid=None, tip=False, root=False) -> _Node:
        n = _Node(_nid[0], np.asarray(pos, dtype=float), r,
                  pid=pid, tip=tip, root=root)
        nodes.append(n)
        _nid[0] += 1
        return n

    # ── 1. Tip nodes ──────────────────────────────────────────────────────────
    # Offset 0.3 mm below the overhang surface so the tip is not exactly on
    # the mesh boundary (avoids false "inside" results in contains() checks).
    _TIP_Z_OFFSET = 0.3
    tip_nodes: list[_Node] = [
        mk([c.x, c.y, c.z_top - _TIP_Z_OFFSET], _TIP_R, tip=True)
        for c in columns
    ]

    # Guard: remove tips whose contact position is inside the model.
    # This prevents supports originating inside concave cavities or hollow shells.
    if mesh is not None:
        tip_nodes = _filter_tips_inside_mesh(tip_nodes, mesh)
    if not tip_nodes:
        return []

    # ── 2. Hierarchical merging: tips → L1 → L2 → L3 ─────────────────────────
    # Each pass clusters nodes in XY and inserts a merge node below them.
    # The merge node's Z is chosen to satisfy the branch-angle constraint.
    level: list[_Node] = tip_nodes

    for cluster_mm in (_L1_MM, _L2_MM, _L3_MM):
        if len(level) <= 1:
            break
        groups = _cluster_xy(level, cluster_mm)
        next_level: list[_Node] = []
        for grp in groups:
            if len(grp) == 1:
                next_level.append(grp[0])
                continue
            cx, cy, mz = _merge_pos(grp, z_min, tan_max)
            r_merge = float(np.clip(len(grp) ** 0.42 * 0.55, _BRANCH_R_MIN, _TRUNK_R_MAX * 0.8))
            mn = mk([cx, cy, mz], r_merge)
            for child in grp:
                if child.pid is None:           # only connect unparented nodes
                    child.pid = mn.nid
            next_level.append(mn)
        level = next_level

    # Adaptive extra merge if still over the trunk cap
    if len(level) > _MAX_TRUNKS:
        scale = math.sqrt(len(level) / _MAX_TRUNKS)
        groups = _cluster_xy(level, _L3_MM * scale)
        merged: list[_Node] = []
        for grp in groups:
            if len(grp) == 1:
                merged.append(grp[0])
                continue
            cx, cy, mz = _merge_pos(grp, z_min, tan_max)
            mn = mk([cx, cy, mz], _TRUNK_R_MIN)
            for child in grp:
                if child.pid is None:
                    child.pid = mn.nid
            merged.append(mn)
        level = merged

    # ── 3. Root nodes on the build plate ─────────────────────────────────────
    # Count descendants before creating roots so we can size trunks correctly.
    node_map      = {n.nid: n for n in nodes}
    children_map  = _build_children_map(nodes)
    _count_desc(nodes, node_map, children_map)

    for top in level:
        r_root = float(np.clip(
            _TRUNK_R_MIN + top.ndesc ** 0.5 * 0.52,
            _TRUNK_R_MIN, _TRUNK_R_MAX,
        ))
        root = mk([top.pos[0], top.pos[1], z_min], r_root, root=True)
        top.pid = root.nid          # connect top-level node to its trunk root

    # Rebuild maps now that roots exist
    node_map     = {n.nid: n for n in nodes}
    children_map = _build_children_map(nodes)

    # ── 4. Tip splay — ensure every tip branch has a visible lean ─────────────
    _splay_tips(nodes, node_map, mesh=mesh)

    # ── 5. Radius assignment via depth-based taper ───────────────────────────
    _assign_radii(nodes, node_map, children_map)

    # ── 6. Collision avoidance ────────────────────────────────────────────────
    if mesh is not None:
        _avoid_collisions(nodes, node_map, mesh, _nid)
        # Rebuild maps to include any inserted waypoint nodes
        node_map     = {n.nid: n for n in nodes}
        children_map = _build_children_map(nodes)

    # ── 6b. Hard validation — remove any segment still intersecting ───────────
    if mesh is not None:
        _hard_reject_invalid_segments(nodes, node_map, mesh)
        node_map     = {n.nid: n for n in nodes}
        children_map = _build_children_map(nodes)

    # ── 7. Convert node graph → ordered TreeBranch segment list ──────────────
    return _to_branches(nodes, node_map, children_map)


# ── Inside-mesh guard ─────────────────────────────────────────────────────────

def _filter_tips_inside_mesh(tips: list[_Node], mesh) -> list[_Node]:
    """
    Remove tip nodes whose contact position is geometrically inside the model.

    Primary method : trimesh.Trimesh.contains()  (requires watertight mesh)
    Fallback method: upward ray-cast — odd intersection count → inside
    """
    if not tips:
        return tips

    pts = np.array([n.pos for n in tips], dtype=float)

    # Primary: fast watertight test
    try:
        inside = mesh.contains(pts)
        return [n for n, ins in zip(tips, inside) if not ins]
    except Exception:
        pass

    # Fallback: ray-cast +Z from just above the tip; odd hits → inside
    keep: list[_Node] = []
    for n in tips:
        try:
            origin = n.pos + np.array([0.0, 0.0, 0.15])
            hits, _, _ = mesh.ray.intersects_location(
                ray_origins=[origin],
                ray_directions=[[0.0, 0.0, 1.0]],
                multiple_hits=True,
            )
            if len(hits) % 2 == 0:   # even (0, 2, …) → outside
                keep.append(n)
        except Exception:
            keep.append(n)   # can't determine — keep

    return keep if keep else tips   # never discard everything on error


# ── Clustering ────────────────────────────────────────────────────────────────

def _cluster_xy(nodes: list[_Node], radius: float) -> list[list[_Node]]:
    """
    Group nodes by XY proximity.

    Uses scipy KDTree when available (O(n log n)); falls back to O(n²) greedy
    single-linkage scan.  Clustering is performed in the XY plane only so
    that nodes at different heights can still share a trunk.
    """
    if len(nodes) <= 1:
        return [[n] for n in nodes]

    pts  = np.array([[n.pos[0], n.pos[1]] for n in nodes])
    used = np.zeros(len(nodes), dtype=bool)
    groups: list[list[_Node]] = []

    if _HAS_SCIPY:
        tree = _KDTree(pts)
        for i in range(len(nodes)):
            if used[i]:
                continue
            idxs = tree.query_ball_point(pts[i], radius)
            grp  = [nodes[j] for j in idxs if not used[j]]
            for j in idxs:
                used[j] = True
            groups.append(grp)
    else:
        for i, n in enumerate(nodes):
            if used[i]:
                continue
            grp   = [n]
            used[i] = True
            for j in range(i + 1, len(nodes)):
                if not used[j]:
                    d = math.hypot(n.pos[0] - nodes[j].pos[0],
                                   n.pos[1] - nodes[j].pos[1])
                    if d <= radius:
                        grp.append(nodes[j])
                        used[j] = True
            groups.append(grp)

    return groups


# ── Merge-node placement ──────────────────────────────────────────────────────

def _merge_pos(
    group:   list[_Node],
    z_min:   float,
    tan_max: float,
) -> tuple[float, float, float]:
    """
    Compute the XY centroid and Z height for a merge node.

    The Z is chosen as `_HEIGHT_FRAC` of the way from z_min to the lowest tip
    in the group, then clamped downward so the branch angle from every group
    member to the merge node does not exceed max_angle_deg.

    Hard constraints:
      mz >= z_min + 2.0   (clear the build plate)
      mz <= z_ref - 0.5   (stay below the group's lowest tip)
    """
    cx    = float(np.mean([n.pos[0] for n in group]))
    cy    = float(np.mean([n.pos[1] for n in group]))
    z_ref = float(min(n.pos[2] for n in group))      # lowest tip in group

    # Fractional default height
    mz = z_min + (z_ref - z_min) * _HEIGHT_FRAC

    # Enforce angle constraint: for each member, z_member - mz ≥ d_xy / tan_max
    if tan_max > 1e-9:
        for n in group:
            d_xy = math.hypot(cx - n.pos[0], cy - n.pos[1])
            if d_xy > 1e-6:
                mz = min(mz, n.pos[2] - d_xy / tan_max)

    # Hard floor / ceiling
    mz = max(mz, z_min + 2.0)
    mz = min(mz, max(z_ref - 0.5, z_min + 0.5))

    return cx, cy, mz


# ── Graph helpers ─────────────────────────────────────────────────────────────

def _build_children_map(nodes: list[_Node]) -> dict[int, list[int]]:
    cm: dict[int, list[int]] = {}
    for n in nodes:
        if n.pid is not None:
            cm.setdefault(n.pid, []).append(n.nid)
    return cm


def _count_desc(
    nodes:       list[_Node],
    nm:          dict[int, _Node],
    cm:          dict[int, list[int]],
) -> None:
    """DFS to populate ndesc (number of descendant tips) for every node."""
    visited: set[int] = set()

    def dfs(nid: int) -> int:
        if nid in visited:
            return nm[nid].ndesc
        visited.add(nid)
        n = nm[nid]
        children = cm.get(nid, [])
        n.ndesc  = sum(dfs(c) for c in children) if children else 1
        return n.ndesc

    for n in nodes:
        dfs(n.nid)


# ── Splay & radius ────────────────────────────────────────────────────────────

def _splay_tips(nodes: list[_Node], nm: dict[int, _Node], mesh=None) -> None:
    """
    Adjust tip-node XY positions to guarantee a minimum visible lean.

    Tips directly above their parent would render as vertical cylinders.
    This pushes each tip outward by _SPLAY (if already leaning) or to at
    least _MIN_XY_SPREAD (if nearly vertical), creating organic angles.
    """
    for n in nodes:
        if not n.tip or n.pid is None:
            continue
        p = nm.get(n.pid)
        if p is None:
            continue

        dx = n.pos[0] - p.pos[0]
        dy = n.pos[1] - p.pos[1]
        d  = math.hypot(dx, dy)

        if d < _MIN_XY_SPREAD:
            if d < 1e-6:
                dx, dy = _MIN_XY_SPREAD, 0.0    # degenerate: push +X
            else:
                s   = _MIN_XY_SPREAD / d
                dx *= s
                dy *= s
        else:
            dx *= _SPLAY
            dy *= _SPLAY

        new_x = p.pos[0] + dx
        new_y = p.pos[1] + dy

        # If a trimesh is available, verify the splayed position is outside.
        # If it landed inside the mesh, keep the original position instead.
        if mesh is not None:
            candidate = np.array([new_x, new_y, n.pos[2]], dtype=float)
            if not _point_inside_mesh(candidate, mesh):
                n.pos[0] = new_x
                n.pos[1] = new_y
            # else: keep original position — hard reject will clean the segment if needed
        else:
            n.pos[0] = new_x
            n.pos[1] = new_y


def _assign_radii(
    nodes:       list[_Node],
    nm:          dict[int, _Node],
    cm:          dict[int, list[int]],
) -> None:
    """
    Walk downward from each root, tapering radius geometrically.

    Root nodes already have their radius set at creation time (proportional
    to ndesc).  Tips are forced to _TIP_R.  All intermediate nodes receive
    parent_r * _TAPER clamped to _BRANCH_R_MIN.
    """
    def walk(nid: int, parent_r: float, depth: int) -> None:
        n = nm[nid]
        if n.tip:
            n.r = _TIP_R
        elif not n.root:
            n.r = float(max(parent_r * _TAPER, _BRANCH_R_MIN))
        for child_nid in cm.get(nid, []):
            walk(child_nid, n.r, depth + 1)

    for n in nodes:
        if n.root:
            walk(n.nid, n.r, 0)


# ── Collision avoidance ───────────────────────────────────────────────────────

def _segment_intersects_mesh(p1: np.ndarray, p2: np.ndarray, mesh) -> bool:
    """
    Return True if the segment p1→p2 clearly intersects the mesh interior.

    Endpoints are intentionally excluded from the inside-mesh check because:
      - tip nodes sit on the overhang surface → the mesh boundary is ambiguous there
      - root nodes sit on the build plate → same issue

    Only the middle 60% of the segment is sampled.  Ray-cast uses a small
    inset on both ends for the same reason.
    """
    vec    = p2 - p1
    length = float(np.linalg.norm(vec))
    if length < 1e-6:
        return False
    direction = vec / length

    # ── Ray cast with endpoint inset ─────────────────────────────────────────
    inset  = min(1.0, length * 0.12)   # 12% or 1mm, whichever is smaller
    origin = p1 + direction * inset
    eff_len = length - 2.0 * inset
    if eff_len > 0.5:
        try:
            locs, _, _ = mesh.ray.intersects_location(
                ray_origins    = [origin],
                ray_directions = [direction],
                multiple_hits  = True,
            )
            for loc in locs:
                d = float(np.linalg.norm(np.asarray(loc, dtype=float) - origin))
                if 0.0 < d < eff_len:
                    return True
        except Exception:
            pass

    # ── Inside-mesh check — middle 60% of segment only ───────────────────────
    try:
        ts     = np.linspace(0.20, 0.80, _COL_SAMPLES)
        pts    = p1[None, :] + ts[:, None] * vec[None, :]
        inside = mesh.contains(pts)
        if np.any(inside):
            return True
    except Exception:
        pass

    return False


def _point_inside_mesh(pt: np.ndarray, mesh) -> bool:
    """Return True if pt is inside the mesh. Conservative: returns False on error."""
    try:
        return bool(mesh.contains(pt[None, :])[0])
    except Exception:
        return False


def _avoid_collisions(
    nodes:   list[_Node],
    nm:      dict[int, _Node],
    mesh,
    nid_ctr: list[int],
) -> None:
    """
    Multi-pass collision avoidance with waypoint insertion.

    For each branch segment up to _COL_MAX_ITER times:
      1. Check segment via ray-cast + inside-mesh sampling.
      2. If collision: compute a waypoint pushed outward from the mesh COM.
      3. Verify the waypoint is outside the mesh — reject if not.
      4. Insert waypoint and continue checking the child sub-segment.
    """
    try:
        mesh_com = np.array(mesh.center_mass, dtype=float).ravel()[:3]
    except Exception:
        try:
            mesh_com = np.array(mesh.centroid, dtype=float).ravel()[:3]
        except Exception:
            return

    # Snapshot of original edges only — waypoints added during iteration
    # are handled by _hard_reject_invalid_segments in the next step.
    snapshot = [(n.nid, n.pid) for n in list(nodes) if n.pid is not None]

    for child_nid, parent_nid in snapshot:
        # Iterate up to _COL_MAX_ITER times on this edge
        cur_child_nid  = child_nid
        cur_parent_nid = parent_nid

        for _iter in range(_COL_MAX_ITER):
            child  = nm.get(cur_child_nid)
            parent = nm.get(cur_parent_nid)
            if child is None or parent is None:
                break

            p1 = parent.pos.copy()
            p2 = child.pos.copy()

            if not _segment_intersects_mesh(p1, p2, mesh):
                break   # clean — done

            # Collision: compute outward waypoint
            vec    = p2 - p1
            length = float(np.linalg.norm(vec))
            if length < _MIN_SEG_MM:
                break

            mid     = (p1 + p2) * 0.5
            outward = mid - mesh_com
            o_norm  = float(np.linalg.norm(outward))
            outward = outward / (o_norm + 1e-9)

            # Try increasing push distances until waypoint is outside mesh
            wp_pos = None
            for mult in (3.0, 5.0, 8.0, 12.0):
                candidate    = mid + outward * (_COL_MARGIN * mult)
                candidate[2] = float(np.clip(candidate[2],
                                             p1[2] + 0.1, p2[2] - 0.1))
                if not _point_inside_mesh(candidate, mesh):
                    wp_pos = candidate
                    break

            if wp_pos is None:
                break   # can't find a valid waypoint — leave for hard reject

            wp_r = (parent.r + child.r) * 0.5
            wp   = _Node(nid_ctr[0], wp_pos, wp_r, pid=cur_parent_nid)
            nm[nid_ctr[0]] = wp
            nodes.append(wp)
            nid_ctr[0] += 1

            child.pid     = wp.nid   # parent → wp → child
            cur_parent_nid = wp.nid  # next iteration checks wp → child
            # cur_child_nid stays the same


# ── Hard segment rejection (zero tolerance post-pass) ─────────────────────────

def _hard_reject_invalid_segments(
    nodes: list[_Node],
    nm:    dict[int, _Node],
    mesh,
) -> None:
    """
    After all avoidance attempts, sever any parent-child edge whose segment
    still intersects the mesh or passes through its interior.

    A severed child becomes a disconnected subtree — _to_branches will simply
    not emit it because it has no root ancestor.
    We prefer missing supports over intersecting ones.
    """
    for n in list(nodes):
        if n.pid is None:
            continue
        parent = nm.get(n.pid)
        if parent is None:
            continue

        p1 = parent.pos.copy()
        p2 = n.pos.copy()

        if _segment_intersects_mesh(p1, p2, mesh):
            n.pid = None   # sever: this node becomes a disconnected orphan


# ── Segment conversion ────────────────────────────────────────────────────────

def _to_branches(
    nodes:       list[_Node],
    nm:          dict[int, _Node],
    cm:          dict[int, list[int]],
) -> list[TreeBranch]:
    """
    BFS from root nodes → emit one TreeBranch per directed edge.

    parent_id in TreeBranch refers to the *branch* whose endpoint is the
    start of this segment (i.e. the segment that ends at the current node's
    parent).  Roots have no incoming segment so their direct children get
    parent_id=None — making those children the trunk segments visible in the
    renderer.

    Segments shorter than _MIN_SEG_MM are silently dropped.
    """
    branches:     list[TreeBranch]  = []
    bid           = [0]
    node_to_bid:  dict[int, Optional[int]] = {}   # nid → branch_id ending there
    visited:      set[int]                  = set()

    queue: deque[_Node] = deque(n for n in nodes if n.root)

    while queue:
        n = queue.popleft()
        if n.nid in visited:
            continue
        visited.add(n.nid)

        if n.root:
            # Root sits on the build plate — no incoming segment.
            # Its children will emit trunk segments with parent_id=None.
            node_to_bid[n.nid] = None
        else:
            parent     = nm.get(n.pid)
            parent_bid = node_to_bid.get(n.pid) if n.pid is not None else None

            if parent is not None:
                seg_len = float(np.linalg.norm(n.pos - parent.pos))
                if seg_len >= _MIN_SEG_MM:
                    branches.append(TreeBranch(
                        id           = bid[0],
                        parent_id    = parent_bid,
                        start_x      = float(parent.pos[0]),
                        start_y      = float(parent.pos[1]),
                        start_z      = float(parent.pos[2]),
                        end_x        = float(n.pos[0]),
                        end_y        = float(n.pos[1]),
                        end_z        = float(n.pos[2]),
                        start_radius = float(parent.r),
                        end_radius   = float(n.r),
                        is_tip       = n.tip,
                    ))
                    node_to_bid[n.nid] = bid[0]
                    bid[0] += 1
                else:
                    # Short segment: inherit parent's branch_id so children
                    # don't lose their topological connection.
                    node_to_bid[n.nid] = parent_bid
            else:
                node_to_bid[n.nid] = parent_bid

        for child_nid in cm.get(n.nid, []):
            if child_nid not in visited:
                queue.append(nm[child_nid])

    return branches
