"""
AutoSlice — Tree Support Engine: Data Models

All coordinates in 3MF space: Z-up, millimetres.
Gravity direction: (0, 0, -1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ── Vec3 — lightweight 3-D vector ────────────────────────────────────────────

@dataclass(frozen=False)
class Vec3:
    x: float
    y: float
    z: float

    # ── Arithmetic ─────────────────────────────────────────────────────────────

    def __add__(self, o: "Vec3") -> "Vec3":
        return Vec3(self.x + o.x, self.y + o.y, self.z + o.z)

    def __sub__(self, o: "Vec3") -> "Vec3":
        return Vec3(self.x - o.x, self.y - o.y, self.z - o.z)

    def __mul__(self, s: float) -> "Vec3":
        return Vec3(self.x * s, self.y * s, self.z * s)

    def __rmul__(self, s: float) -> "Vec3":
        return self.__mul__(s)

    def __truediv__(self, s: float) -> "Vec3":
        return Vec3(self.x / s, self.y / s, self.z / s)

    def __neg__(self) -> "Vec3":
        return Vec3(-self.x, -self.y, -self.z)

    def __iter__(self):
        return iter((self.x, self.y, self.z))

    def __repr__(self) -> str:
        return f"Vec3({self.x:.3f}, {self.y:.3f}, {self.z:.3f})"

    # ── Geometry ───────────────────────────────────────────────────────────────

    def dot(self, o: "Vec3") -> float:
        return self.x * o.x + self.y * o.y + self.z * o.z

    def cross(self, o: "Vec3") -> "Vec3":
        return Vec3(
            self.y * o.z - self.z * o.y,
            self.z * o.x - self.x * o.z,
            self.x * o.y - self.y * o.x,
        )

    def length(self) -> float:
        return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)

    def length_sq(self) -> float:
        return self.x ** 2 + self.y ** 2 + self.z ** 2

    def normalize(self) -> "Vec3":
        l = self.length()
        if l < 1e-10:
            return Vec3(0.0, 0.0, 1.0)
        return Vec3(self.x / l, self.y / l, self.z / l)

    def lerp(self, o: "Vec3", t: float) -> "Vec3":
        return self + (o - self) * t

    def xy_dist(self, o: "Vec3") -> float:
        return math.sqrt((self.x - o.x) ** 2 + (self.y - o.y) ** 2)

    def dist(self, o: "Vec3") -> float:
        return (self - o).length()

    # ── Serialisation ──────────────────────────────────────────────────────────

    def to_list(self) -> List[float]:
        return [self.x, self.y, self.z]

    @staticmethod
    def from_list(lst: List[float]) -> "Vec3":
        return Vec3(lst[0], lst[1], lst[2])

    @staticmethod
    def zero() -> "Vec3":
        return Vec3(0.0, 0.0, 0.0)

    @staticmethod
    def min_v(a: "Vec3", b: "Vec3") -> "Vec3":
        return Vec3(min(a.x, b.x), min(a.y, b.y), min(a.z, b.z))

    @staticmethod
    def max_v(a: "Vec3", b: "Vec3") -> "Vec3":
        return Vec3(max(a.x, b.x), max(a.y, b.y), max(a.z, b.z))


# ── Gravity (3MF Z-up) ────────────────────────────────────────────────────────

GRAVITY = Vec3(0.0, 0.0, -1.0)


# ── Support domain models ─────────────────────────────────────────────────────

@dataclass
class OverhangFace:
    """One triangle that needs external support."""
    index:       int
    centroid:    Vec3
    normal:      Vec3         # points downward (dot with gravity > 0)
    area:        float        # mm²
    overhang_dot: float       # dot(normal, gravity): 0=horizontal, 1=straight down


@dataclass
class SupportCluster:
    """A connected island of overhang faces → one support target."""
    id:          int
    centroid:    Vec3
    area:        float        # total face area, mm²
    face_count:  int
    tip_position: Vec3        # centroid offset toward support approach
    avg_normal:  Vec3
    bbox_min:    Vec3
    bbox_max:    Vec3
    severity:    str          # "minor" | "moderate" | "severe" | "critical"


@dataclass
class SupportNode:
    """Node in the tree support graph."""
    id:          int
    position:    Vec3
    radius:      float        # mm
    parent_id:   Optional[int]
    child_ids:   List[int]    = field(default_factory=list)
    node_type:   str          = "branch"   # root|trunk|branch|tip|contact|waypoint
    cluster_id:  Optional[int] = None      # set for tip/contact nodes
    depth:       int           = 0         # BFS depth from root


@dataclass
class SupportSegment:
    """Directed segment connecting two nodes (parent → child direction)."""
    id:            int
    start_node_id: int
    end_node_id:   int
    radius_start:  float
    radius_end:    float
    length:        float
    is_trunk:      bool = False


@dataclass
class SupportContact:
    """Minimal contact interface between a support tip and an overhang."""
    id:         int
    cluster_id: int
    node_id:    int
    position:   Vec3
    radius:     float
    normal:     Vec3           # outward from model surface


# ── Engine configuration ──────────────────────────────────────────────────────

@dataclass
class EngineConfig:
    # ── Overhang detection ────────────────────────────────────────────────────
    overhang_angle_deg:      float = 45.0
    floor_margin_mm:         float = 1.0
    min_cluster_area_mm2:    float = 4.0
    cluster_cell_mm:         float = 5.0
    verify_unsupported:      bool  = True   # ray-cast below each cluster
    # ── Tree geometry ─────────────────────────────────────────────────────────
    branch_angle_deg:        float = 40.0
    trunk_radius_min_mm:     float = 1.6
    trunk_radius_max_mm:     float = 4.5
    branch_radius_mm:        float = 1.0
    tip_radius_mm:           float = 0.5
    contact_radius_mm:       float = 0.4
    collision_margin_mm:     float = 0.8
    # ── Merge radii (3-level) ────────────────────────────────────────────────
    merge_l1_mm:             float = 15.0   # tip → sub-branch
    merge_l2_mm:             float = 35.0   # sub-branch → branch
    merge_l3_mm:             float = 70.0   # branch → trunk
    # ── Z / XY gaps ──────────────────────────────────────────────────────────
    z_distance_mm:           float = 0.2
    xy_distance_mm:          float = 0.4
    # ── Tapering ─────────────────────────────────────────────────────────────
    taper:                   float = 0.74
    branch_frac:             float = 0.55   # trunk-top at this fraction of height
    min_xz_spread_mm:        float = 3.0
    splay_mult:              float = 1.20
    # ── Minimum printable size ────────────────────────────────────────────────
    nozzle_diameter_mm:      float = 0.4
    layer_height_mm:         float = 0.2
    min_segment_mm:          float = 1.5
    # ── Collision avoidance ───────────────────────────────────────────────────
    enable_collision_avoidance: bool = True
    collision_waypoint_offset_mult: float = 3.0


# ── Plan output ───────────────────────────────────────────────────────────────

@dataclass
class SupportStats:
    cluster_count:       int
    trunk_count:         int
    branch_count:        int
    tip_count:           int
    contact_count:       int
    node_count:          int
    segment_count:       int
    estimated_volume_mm3: float


@dataclass
class TreeSupportPlan:
    support_type:    str           # "tree" | "standard" | "none"
    decision_reason: str
    clusters:        List[SupportCluster]
    nodes:           List[SupportNode]
    segments:        List[SupportSegment]
    contacts:        List[SupportContact]
    stats:           SupportStats
    warnings:        List[str]     = field(default_factory=list)
