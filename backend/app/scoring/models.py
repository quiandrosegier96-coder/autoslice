"""
AutoSlice — Pydantic models for the scoring and diagnostic layer.

Hierarchy:
  GeometryFeatures  →  RiskScores  →  SettingsDecisions  →  GenerationReport

These are FastAPI-compatible Pydantic models. The existing internal
dataclasses (GeometryAnalysis, ModelIntent, PrintSettings) remain for
the rules engine; these models are the structured API and audit layer.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field
from app.scoring.printability import PrintabilityScore
from app.explain.models import ExplanationReport
from app.orientation.models import OrientationReport


# ─────────────────────────────────────────────────────────────────────────────
# Risk level enum
# ─────────────────────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    NONE   = "none"    # 0–14
    LOW    = "low"     # 15–34
    MEDIUM = "medium"  # 35–59
    HIGH   = "high"    # 60–100


def risk_level(value: int) -> RiskLevel:
    if value >= 60:
        return RiskLevel.HIGH
    if value >= 35:
        return RiskLevel.MEDIUM
    if value >= 15:
        return RiskLevel.LOW
    return RiskLevel.NONE


# ─────────────────────────────────────────────────────────────────────────────
# Geometry feature models
# ─────────────────────────────────────────────────────────────────────────────

class BoundingBox(BaseModel):
    x_mm:       float
    y_mm:       float
    z_mm:       float
    volume_cm3: float


class OverhangFeatures(BaseModel):
    has_overhangs:              bool
    max_angle_deg:              float
    overhang_area_ratio:        float = Field(ge=0.0, le=1.0)
    mild_area_ratio:            float = Field(default=0.0, ge=0.0, le=1.0)
    moderate_area_ratio:        float = Field(default=0.0, ge=0.0, le=1.0)
    severe_area_ratio:          float = Field(default=0.0, ge=0.0, le=1.0)
    estimated_support_area_mm2: float = 0.0


class BridgeFeatures(BaseModel):
    has_bridges:     bool
    max_span_mm:     float
    bridge_area_mm2: float = 0.0
    cluster_count:   int   = 0


class ThinWallFeatures(BaseModel):
    has_thin_walls:   bool
    min_thickness_mm: float


class GeometryFeatures(BaseModel):
    bounding_box:           BoundingBox
    part_count:             int
    mesh_is_watertight:     bool
    estimated_volume_cm3:   float
    surface_area_mm2:       float
    contact_area_mm2:       float
    height_to_base_ratio:   float
    slenderness_ratio:      float = 0.0
    center_of_mass_z_ratio: float = 0.5
    overhang:               OverhangFeatures
    bridge:                 BridgeFeatures
    thin_wall:              ThinWallFeatures

    @classmethod
    def from_geometry_analysis(cls, geo: object) -> GeometryFeatures:
        """
        Construct from the internal GeometryAnalysis dataclass so the
        scoring layer does not depend on the dataclass schema directly.
        """
        bb = geo.bounding_box
        return cls(
            bounding_box=BoundingBox(
                x_mm=bb.x_mm, y_mm=bb.y_mm,
                z_mm=bb.z_mm, volume_cm3=bb.volume_cm3,
            ),
            part_count=geo.part_count,
            mesh_is_watertight=geo.mesh_is_watertight,
            estimated_volume_cm3=geo.estimated_volume_cm3,
            surface_area_mm2=geo.surface_area_mm2,
            contact_area_mm2=geo.contact_area_mm2,
            height_to_base_ratio=geo.height_to_base_ratio,
            slenderness_ratio=geo.slenderness_ratio,
            center_of_mass_z_ratio=geo.center_of_mass_z_ratio,
            overhang=OverhangFeatures(
                has_overhangs=geo.overhang.has_overhangs,
                max_angle_deg=geo.overhang.max_angle_deg,
                overhang_area_ratio=geo.overhang.overhang_area_ratio,
                mild_area_ratio=geo.overhang.mild_area_ratio,
                moderate_area_ratio=geo.overhang.moderate_area_ratio,
                severe_area_ratio=geo.overhang.severe_area_ratio,
                estimated_support_area_mm2=geo.overhang.estimated_support_area_mm2,
            ),
            bridge=BridgeFeatures(
                has_bridges=geo.bridge.has_bridges,
                max_span_mm=geo.bridge.max_span_mm,
                bridge_area_mm2=geo.bridge.bridge_area_mm2,
                cluster_count=geo.bridge.cluster_count,
            ),
            thin_wall=ThinWallFeatures(
                has_thin_walls=geo.thin_wall.has_thin_walls,
                min_thickness_mm=geo.thin_wall.min_thickness_mm,
            ),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Risk score models
# ─────────────────────────────────────────────────────────────────────────────

class RiskScore(BaseModel):
    value:   int = Field(ge=0, le=100)
    level:   RiskLevel
    reasons: list[str]   # ordered list of contributing factors


class RiskScores(BaseModel):
    support:   RiskScore
    bridge:    RiskScore   # bridge-specific quality risk (separate from support)
    adhesion:  RiskScore
    stability: RiskScore
    detail:    RiskScore

    @property
    def max_value(self) -> int:
        return max(
            self.support.value,
            self.bridge.value,
            self.adhesion.value,
            self.stability.value,
            self.detail.value,
        )

    @property
    def difficulty(self) -> Literal["easy", "moderate", "hard"]:
        m = self.max_value
        if m >= 60:
            return "hard"
        if m >= 35:
            return "moderate"
        return "easy"


# ─────────────────────────────────────────────────────────────────────────────
# Settings decision models
# Each decision carries the reasons that drove it — the audit trail.
# ─────────────────────────────────────────────────────────────────────────────

class SupportDecision(BaseModel):
    enabled:             bool
    type:                Literal["normal", "tree", "none"]
    placement:           Literal["buildplate_only", "everywhere"] = "buildplate_only"
    density_percent:     int
    angle_threshold_deg: int
    interface_enabled:   bool
    interface_layers:    int
    top_z_distance_mm:   float
    xy_distance_mm:      float
    reasons:             list[str]


class BrimDecision(BaseModel):
    enabled:  bool
    width_mm: float
    reasons:  list[str]


class LayerDecision(BaseModel):
    height_mm: float
    reasons:   list[str]


class WallDecision(BaseModel):
    count:         int
    top_layers:    int
    bottom_layers: int
    reasons:       list[str]


class InfillDecision(BaseModel):
    percent: int
    pattern: str
    reasons: list[str]


class SpeedDecision(BaseModel):
    print_mm_s:      int
    fan_percent:     int
    min_layer_time_s: int
    reasons:         list[str]


class QualityDecision(BaseModel):
    ironing_enabled:      bool
    top_surface_pattern:  Literal["monotonic", "concentric"]
    seam_position:        Literal["aligned", "nearest"]
    reasons:              list[str]


class LineWidthDecision(BaseModel):
    line_width_mm:           float   # wall / perimeter width
    first_layer_width_mm:    float   # first layer (wider for adhesion)
    infill_width_mm:         float   # infill (slightly wider, speed-focused)
    reasons:                 list[str]


class SettingsDecisions(BaseModel):
    support:    SupportDecision
    brim:       BrimDecision
    layer:      LayerDecision
    walls:      WallDecision
    infill:     InfillDecision
    speed:      SpeedDecision
    quality:    QualityDecision
    line_width: LineWidthDecision


# ─────────────────────────────────────────────────────────────────────────────
# Generation report — full audit record for one conversion
# ─────────────────────────────────────────────────────────────────────────────

class DecisionEntry(BaseModel):
    """One rule firing from the engine's DecisionTrace."""
    rule:    str
    trigger: str
    field:   str
    before:  object
    after:   object


class GenerationReport(BaseModel):
    job_id:         str
    printer_id:     str
    filament:       str
    nozzle_mm:      float
    geometry:       GeometryFeatures
    risk_scores:    RiskScores
    difficulty:     Literal["easy", "moderate", "hard"]
    printability:   PrintabilityScore
    explanations:   ExplanationReport
    orientation:    OrientationReport
    decisions:      SettingsDecisions
    decision_trace: list[DecisionEntry]
    settings_delta: dict[str, object]
    generated_at:   datetime
