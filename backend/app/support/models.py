"""
AutoSlice — Support preview data models.
Returned by GET /api/analyze/{job_id}/support-preview.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class SupportColumn(BaseModel):
    x:        float   # 3MF coordinate space (Z-up, mm)
    y:        float
    z_bottom: float   # base of column — z_min or just above hit geometry
    z_top:    float   # underside of the overhang
    radius:   float   # mm


class TreeBranch(BaseModel):
    """
    One segment of a tree support skeleton.

    Coordinates are in 3MF space (Z-up, mm).  The frontend applies the same
    -π/2 X-rotation + center-subtraction used for all support geometry.

    Hierarchy
    ---------
    parent_id is None  → root trunk (starts at build plate, z = z_min)
    parent_id is set   → sub-trunk or tip branch extending from parent's end
    is_tip = True      → contact point with the model's overhang surface
    """
    id:           int
    parent_id:    Optional[int] = None

    # 3MF-space coordinates (Z-up, mm)
    start_x:      float
    start_y:      float
    start_z:      float
    end_x:        float
    end_y:        float
    end_z:        float

    # Radius at start and end — wider at root, narrower toward tips
    start_radius: float
    end_radius:   float

    # True when this branch terminates at an overhang contact point
    is_tip:       bool = False


class SupportDebugLayers(BaseModel):
    """
    Extra data attached when the endpoint is called with ?debug=true.
    Positions are flat float buffers in 3MF space (Z-up, mm), same coordinate
    convention as overhang_positions.  The frontend applies the same
    -π/2 X-rotation + center-subtraction to align them with the model.
    """
    # All detected overhang triangles BEFORE the self-support and floor filters
    # (flat buffer: 9 floats per triangle, same layout as overhang_positions)
    all_overhang_positions: list[float]

    # Flat [x,y,z, x,y,z, ...] — cluster centroids that received a column
    active_candidate_points: list[float]

    # Flat [x,y,z, x,y,z, ...] — cluster centroids that were filtered out
    # (self-supported, too-short column, floor zone)
    filtered_candidate_points: list[float]


class SupportPreviewData(BaseModel):
    job_id:         str
    needs_supports: bool
    support_type:   str   # "none" | "normal" | "tree"
    placement:      str   # "buildplate_only" | "everywhere"

    # Flat buffer: groups of 9 floats per triangle [x1,y1,z1, x2,y2,z2, x3,y3,z3, ...]
    # All in 3MF coordinate space (Z-up). Frontend applies the -π/2 X rotation + centering.
    overhang_positions: list[float]
    overhang_severity:  list[str]   # one entry per triangle: "mild" | "moderate" | "severe"

    support_columns:    list[SupportColumn]

    # Tree support skeleton — populated when support_type == "tree"
    tree_branches:      list[TreeBranch] = []
    trunk_count:        int = 0   # number of root trunks (parent_id is None)
    tip_count:          int = 0   # number of model-contact tips (is_tip=True)

    # Bounding-box center in 3MF space — frontend converts to Three.js space and subtracts
    # this to match the centering that AutoCamera applies to the loaded model.
    model_center:       list[float]   # [cx, cy, cz]

    overhang_area_mm2:  float
    column_count:       int

    # Only populated when the endpoint is called with ?debug=true
    debug: Optional[SupportDebugLayers] = None
