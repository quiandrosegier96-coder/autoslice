"""
AutoSlice — Pydantic schemas for the AI auto-settings module.

Request/response contract for POST /ai/auto-settings.

Hierarchy:
  ModelFeatures  →  AutoSettingsRequest
  AIGeneratedSettings + PrintRiskScore + list[PrintWarning]
    + ConvertHints  →  AutoSettingsResponse

ConvertHints is the Apply AI Settings bridge: it carries the exact subset of
ConvertRequest fields that the AI can meaningfully suggest (filament, nozzle size,
nozzle type, build plate).  Everything else (layer height, infill, supports, speeds)
is advisory-only — displayed to the user but computed by the rules engine at convert
time.  The rules engine remains authoritative; slicing behaviour only changes when
the user explicitly applies the hints.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    NONE   = "none"    # 0–14
    LOW    = "low"     # 15–34
    MEDIUM = "medium"  # 35–59
    HIGH   = "high"    # 60–100


class WarningSeverity(str, Enum):
    INFO    = "info"
    WARNING = "warning"
    ERROR   = "error"


class FilamentType(str, Enum):
    PLA   = "pla"
    PETG  = "petg"
    ABS   = "abs"
    ASA   = "asa"
    TPU   = "tpu"
    NYLON = "nylon"


# ─────────────────────────────────────────────────────────────────────────────
# Request
# ─────────────────────────────────────────────────────────────────────────────

class ModelFeatures(BaseModel):
    """Geometry-derived features extracted from the uploaded model."""

    height_mm:       float = Field(gt=0,        description="Total model height in millimetres.")
    volume_cm3:      float = Field(gt=0,        description="Estimated model volume in cubic centimetres.")
    overhang_ratio:  float = Field(ge=0.0, le=1.0, description="Fraction of surface area classified as overhang (0–1).")
    thin_wall_ratio: float = Field(ge=0.0, le=1.0, description="Fraction of surface area with wall thickness below the nozzle diameter (0–1).")


class AutoSettingsRequest(BaseModel):
    """Input payload for the AI auto-settings endpoint."""

    features:        ModelFeatures
    filament:        FilamentType = FilamentType.PLA
    nozzle_mm:       float        = Field(default=0.4, gt=0, description="Nozzle diameter in millimetres.")
    quality_intent:  Literal["draft", "standard", "quality"] = "standard"


# ─────────────────────────────────────────────────────────────────────────────
# Generated settings
# ─────────────────────────────────────────────────────────────────────────────

class AILayerSettings(BaseModel):
    height_mm:             float
    first_layer_height_mm: float


class AISupportSettings(BaseModel):
    enabled:             bool
    type:                Literal["normal", "tree", "none"]
    density_percent:     int
    angle_threshold_deg: int


class AIAdhesionSettings(BaseModel):
    brim_enabled: bool
    brim_width_mm: float


class AIInfillSettings(BaseModel):
    percent: int
    pattern: str


class AISpeedSettings(BaseModel):
    print_mm_s:       int
    first_layer_mm_s: int
    fan_percent:      int


class AIGeneratedSettings(BaseModel):
    """Suggested slicer parameters produced by the AI engine."""

    layer:    AILayerSettings
    support:  AISupportSettings
    adhesion: AIAdhesionSettings
    infill:   AIInfillSettings
    speed:    AISpeedSettings
    wall_count:    int
    top_layers:    int
    bottom_layers: int
    nozzle_temp_c: int
    bed_temp_c:    int


# ─────────────────────────────────────────────────────────────────────────────
# Risk score
# ─────────────────────────────────────────────────────────────────────────────

class DimensionRisk(BaseModel):
    """Risk contribution from a single geometry dimension."""

    label: str
    value: int   = Field(ge=0, le=100)
    level: RiskLevel


class PrintRiskScore(BaseModel):
    """Composite print risk assessment derived from model features."""

    overall:  int        = Field(ge=0, le=100)
    level:    RiskLevel
    overhang: DimensionRisk
    thin_wall: DimensionRisk
    stability: DimensionRisk
    volume:   DimensionRisk


# ─────────────────────────────────────────────────────────────────────────────
# Warnings
# ─────────────────────────────────────────────────────────────────────────────

class PrintWarning(BaseModel):
    """A single actionable warning raised by the AI engine."""

    code:     str            # machine-readable identifier, e.g. "HIGH_OVERHANG"
    severity: WarningSeverity
    message:  str            # human-readable explanation
    field:    str | None = None  # optional: which feature triggered this warning


# ─────────────────────────────────────────────────────────────────────────────
# Convert hints — the Apply AI Settings bridge
#
# These are the only ConvertRequest fields the AI can meaningfully suggest.
# All other slicer parameters (layer height, infill %, wall count, speeds,
# temps, supports) are internal outputs of the rules engine and are NOT
# present in ConvertRequest — they cannot be passed in by the frontend.
#
# Frontend usage:
#   1. Receive AutoSettingsResponse
#   2. Display settings + warnings to user
#   3. On "Apply AI Settings" click, merge convert_hints into the convert form:
#        form.filament_type  = hints.filament_type
#        form.nozzle_size_mm = hints.nozzle_size_mm
#        form.nozzle_type    = hints.nozzle_type
#        form.build_plate    = hints.build_plate
#   4. User reviews the pre-filled form and submits normally via POST /api/convert
#   5. Rules engine runs unchanged with the user-confirmed inputs
# ─────────────────────────────────────────────────────────────────────────────

class ConvertHints(BaseModel):
    """
    Pre-populated subset of ConvertRequest suggested by the AI engine.
    Merge into the convert form on 'Apply AI Settings'; submit unchanged
    via the normal POST /api/convert flow.
    """

    filament_type:  str   = Field(description="Recommended filament type. Maps to ConvertRequest.filament_type.")
    nozzle_size_mm: float = Field(gt=0, description="Recommended nozzle diameter in mm. Maps to ConvertRequest.nozzle_size_mm.")
    nozzle_type:    str   = Field(description="Recommended nozzle material. Maps to ConvertRequest.nozzle_type.")
    build_plate:    str   = Field(description="Recommended build plate surface. Maps to ConvertRequest.build_plate.")


# ─────────────────────────────────────────────────────────────────────────────
# Response
# ─────────────────────────────────────────────────────────────────────────────

class AutoSettingsResponse(BaseModel):
    """Full response returned by POST /ai/auto-settings."""

    settings:      AIGeneratedSettings
    risk:          PrintRiskScore
    warnings:      list[PrintWarning]
    convert_hints: ConvertHints
    engine_version: str = "1.0.0"
