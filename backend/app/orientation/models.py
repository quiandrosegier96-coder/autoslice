"""
AutoSlice — Orientation optimization data models.
"""

from __future__ import annotations

from pydantic import BaseModel


class OrientationCandidate(BaseModel):
    label:               str
    rotation_euler_deg:  list[float]        # [rx, ry, rz] degrees applied to the mesh
    overhang_area_ratio: float              # fraction of surface area that overhangs
    contact_area_mm2:    float              # XY-projected area touching the build plate
    height_to_base_ratio: float            # z / sqrt(contact_area) — stability indicator
    height_mm:           float             # print height in this orientation
    support_score:       int               # 0–100 (higher = less overhang)
    adhesion_score:      int               # 0–100 (higher = better contact)
    stability_score:     int               # 0–100 (higher = lower HBR)
    height_score:        int               # 0–100 (higher = shorter print)
    total_score:         int               # weighted composite, 0–100


class OrientationReport(BaseModel):
    recommended:          OrientationCandidate
    original:             OrientationCandidate
    all_candidates:       list[OrientationCandidate]
    improvement:          int              # recommended.total - original.total
    should_rotate:        bool             # True if improvement >= 10 and orientation differs
    support_reduction_pct: float          # overhang reduction vs original (%)
    reasons:              list[str]        # human-readable sentences
