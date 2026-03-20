"""
AutoSlice — Tree Support Engine: Serializer

Converts a TreeSupportPlan into:
  - A JSON-serialisable dict (for API responses and frontend preview)
  - Optional skeleton-only data (lightweight, for initial viewer load)

Output format:
  {
    "supportType":    "tree" | "standard" | "none",
    "decisionReason": "...",
    "clusters":  [...],
    "nodes":     [...],
    "segments":  [...],
    "contacts":  [...],
    "stats":     { estimatedVolumeMm3, trunkCount, ... },
    "warnings":  [...],
  }
"""

from __future__ import annotations

import math
from typing import Any, Dict

from .models import SupportStats, TreeSupportPlan


def serialise(plan: TreeSupportPlan) -> Dict[str, Any]:
    """Full serialisation — includes all node/segment detail."""
    return {
        "supportType":    plan.support_type,
        "decisionReason": plan.decision_reason,
        "clusters":       [_cluster(c)  for c in plan.clusters],
        "nodes":          [_node(n)     for n in plan.nodes],
        "segments":       [_segment(s)  for s in plan.segments],
        "contacts":       [_contact(ct) for ct in plan.contacts],
        "stats":          _stats(plan.stats),
        "warnings":       plan.warnings,
    }


def serialise_skeleton(plan: TreeSupportPlan) -> Dict[str, Any]:
    """Lightweight skeleton — segments + stats only (for initial preview)."""
    return {
        "supportType":    plan.support_type,
        "decisionReason": plan.decision_reason,
        "segments":       [_segment(s)  for s in plan.segments],
        "stats":          _stats(plan.stats),
        "warnings":       plan.warnings,
    }


def compute_stats(plan: TreeSupportPlan) -> SupportStats:
    """Recompute accurate stats from the finalised plan."""
    trunk_count  = sum(1 for n in plan.nodes if n.node_type in ("root", "trunk"))
    branch_count = sum(1 for n in plan.nodes if n.node_type == "branch")
    tip_count    = sum(1 for n in plan.nodes if n.node_type == "tip")
    contact_count= sum(1 for n in plan.nodes if n.node_type == "contact")

    node_map = {n.id: n for n in plan.nodes}
    volume   = _estimate_volume(plan.segments, node_map)

    return SupportStats(
        cluster_count        = len(plan.clusters),
        trunk_count          = trunk_count,
        branch_count         = branch_count,
        tip_count            = tip_count,
        contact_count        = contact_count,
        node_count           = len(plan.nodes),
        segment_count        = len(plan.segments),
        estimated_volume_mm3 = volume,
    )


# ── Per-object serialisers ────────────────────────────────────────────────────

def _cluster(c) -> Dict[str, Any]:
    return {
        "id":          c.id,
        "centroid":    c.centroid.to_list(),
        "area":        round(c.area, 2),
        "faceCount":   c.face_count,
        "tipPosition": c.tip_position.to_list(),
        "avgNormal":   c.avg_normal.to_list(),
        "bboxMin":     c.bbox_min.to_list(),
        "bboxMax":     c.bbox_max.to_list(),
        "severity":    c.severity,
    }


def _node(n) -> Dict[str, Any]:
    return {
        "id":        n.id,
        "position":  n.position.to_list(),
        "radius":    round(n.radius, 3),
        "parentId":  n.parent_id,
        "childIds":  n.child_ids,
        "type":      n.node_type,
        "clusterId": n.cluster_id,
        "depth":     n.depth,
    }


def _segment(s) -> Dict[str, Any]:
    return {
        "id":           s.id,
        "startNodeId":  s.start_node_id,
        "endNodeId":    s.end_node_id,
        "radiusStart":  round(s.radius_start, 3),
        "radiusEnd":    round(s.radius_end, 3),
        "length":       round(s.length, 2),
        "isTrunk":      s.is_trunk,
    }


def _contact(ct) -> Dict[str, Any]:
    return {
        "id":        ct.id,
        "clusterId": ct.cluster_id,
        "nodeId":    ct.node_id,
        "position":  ct.position.to_list(),
        "radius":    round(ct.radius, 3),
        "normal":    ct.normal.to_list(),
    }


def _stats(s: SupportStats) -> Dict[str, Any]:
    return {
        "clusterCount":       s.cluster_count,
        "trunkCount":         s.trunk_count,
        "branchCount":        s.branch_count,
        "tipCount":           s.tip_count,
        "contactCount":       s.contact_count,
        "nodeCount":          s.node_count,
        "segmentCount":       s.segment_count,
        "estimatedVolumeMm3": round(s.estimated_volume_mm3, 1),
        "estimatedVolumeCm3": round(s.estimated_volume_mm3 / 1000.0, 3),
    }


# ── Volume estimation ─────────────────────────────────────────────────────────

def _estimate_volume(segments, node_map) -> float:
    """Sum of truncated-cone volumes: V = π/3 × h × (r1² + r1r2 + r2²)."""
    vol = 0.0
    for seg in segments:
        a = node_map.get(seg.start_node_id)
        b = node_map.get(seg.end_node_id)
        if not a or not b:
            continue
        h  = seg.length
        r1 = seg.radius_start
        r2 = seg.radius_end
        vol += (math.pi / 3.0) * h * (r1 * r1 + r1 * r2 + r2 * r2)
    return vol
