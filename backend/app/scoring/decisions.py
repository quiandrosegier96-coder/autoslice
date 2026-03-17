"""
AutoSlice — Rule-based settings decision module.

compute_settings_decisions(features, scores, base) → SettingsDecisions

Pure functions. No side effects. No I/O.
Takes geometry features + risk scores and returns structured per-domain
decisions, each with an ordered list of reasons.

Base values (layer height, speed, etc.) are passed in from the caller
so this module works with any printer profile — it only applies geometry
and risk-driven adjustments on top of whatever base was loaded.
"""

from __future__ import annotations

from typing import Literal

from app.scoring.models import (
    BrimDecision,
    GeometryFeatures,
    InfillDecision,
    LayerDecision,
    LineWidthDecision,
    QualityDecision,
    RiskScores,
    SettingsDecisions,
    SpeedDecision,
    SupportDecision,
    WallDecision,
)


def compute_settings_decisions(
    features:              GeometryFeatures,
    scores:                RiskScores,
    nozzle_mm:             float = 0.4,
    base_speed_mm_s:       int   = 200,
    base_layer_height_mm:  float = 0.2,
    base_fan_percent:      int   = 100,
    base_wall_count:       int   = 3,
    base_infill_percent:   int   = 15,
    base_top_layers:       int   = 5,
    base_bottom_layers:    int   = 4,
) -> SettingsDecisions:
    return SettingsDecisions(
        support    = _decide_support(features, scores),
        brim       = _decide_brim(features, scores),
        layer      = _decide_layer(features, scores, base_layer_height_mm),
        walls      = _decide_walls(features, scores, base_wall_count, base_top_layers, base_bottom_layers),
        infill     = _decide_infill(features, scores, base_infill_percent),
        speed      = _decide_speed(features, scores, base_speed_mm_s, base_fan_percent),
        quality    = _decide_quality(features, scores),
        line_width = _decide_line_width(features, scores, nozzle_mm),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Support
# ─────────────────────────────────────────────────────────────────────────────

def _decide_support(f: GeometryFeatures, s: RiskScores) -> SupportDecision:
    reasons: list[str] = []
    ov = f.overhang

    # Trigger on moderate or severe overhang zones, or high support risk
    needs_supports = (
        ov.moderate_area_ratio > 0.02 or
        ov.severe_area_ratio   > 0.005 or
        ov.max_angle_deg       > 55 or
        s.support.value        >= 35
    )

    if not needs_supports:
        return SupportDecision(
            enabled=False, type="none",
            placement="buildplate_only",
            density_percent=0, angle_threshold_deg=50,
            interface_enabled=False, interface_layers=0,
            top_z_distance_mm=0.2, xy_distance_mm=0.35,
            reasons=["No significant overhangs — supports not needed"],
        )

    reasons.append(f"support_risk={s.support.value}")

    # Support type: tree for severe/organic overhangs, normal for moderate/mechanical
    if s.support.value >= 60 or ov.severe_area_ratio > 0.03 or ov.overhang_area_ratio > 0.10:
        stype: Literal["normal", "tree", "none"] = "tree"
        reasons.append(
            f"Tree supports: severe_ratio={ov.severe_area_ratio:.1%}"
            f" or overhang_ratio={ov.overhang_area_ratio:.1%}"
            f" or support_risk={s.support.value} >= 60"
        )
    else:
        stype = "normal"
        reasons.append("Normal supports: moderate overhang geometry")

    # Density: based on severity tiers + support risk score
    if s.support.value >= 70 or ov.severe_area_ratio > 0.05:
        density = 25
        reasons.append("Heavy density 25%: support_risk >= 70 or extensive severe overhangs")
    elif s.support.value >= 35 or ov.moderate_area_ratio > 0.05:
        density = 15
        reasons.append("Normal density 15%: support_risk >= 35")
    else:
        density = 10
        reasons.append("Light density 10%: low support_risk")

    # Angle threshold: tighten for bridges or severe overhangs
    if f.bridge.max_span_mm > 15 or ov.severe_area_ratio > 0.02:
        angle = 40
        reasons.append(
            f"Tighter angle 40°: bridge_span={f.bridge.max_span_mm:.1f}mm > 15mm"
            f" or severe_overhang={ov.severe_area_ratio:.1%}"
        )
    elif ov.moderate_area_ratio > 0.05:
        angle = 45
        reasons.append("Angle 45°: moderate overhang zone significant")
    else:
        angle = 50

    # Interface layers
    iface_layers = 3 if s.support.value >= 50 else 2
    reasons.append(f"Interface: {iface_layers} concentric layers for clean removal")

    # Z gap: tighter for complex geometry (better surface), wider for trivial overhangs
    if s.support.value >= 60:
        top_z = 0.2
        reasons.append("Z gap 0.2mm: high support_risk — tight for better surface quality")
    elif s.support.value <= 20:
        top_z = 0.25
        reasons.append("Z gap 0.25mm: low support_risk — relaxed for easy removal")
    else:
        top_z = 0.2

    # Support placement: "everywhere" when overhangs appear on vertical or
    # hanging faces that aren't reachable by growing up from the build plate.
    # Heuristic: high overhang_area_ratio on a model with non-trivial moderate
    # zone → overhangs are distributed across the model, not just at the base.
    if (
        ov.overhang_area_ratio > 0.15 or
        (ov.severe_area_ratio > 0.01 and s.support.value >= 50) or
        (ov.moderate_area_ratio > 0.10 and s.support.value >= 60)
    ):
        placement: Literal["buildplate_only", "everywhere"] = "everywhere"
        reasons.append(
            "Support placement: everywhere — overhang geometry distributed across the model, "
            "not reachable by buildplate-only supports"
        )
    else:
        placement = "buildplate_only"
        reasons.append(
            "Support placement: buildplate_only — overhangs are reachable from below, "
            "reducing support volume and removal difficulty"
        )

    return SupportDecision(
        enabled=True, type=stype,
        placement=placement,
        density_percent=density,
        angle_threshold_deg=angle,
        interface_enabled=True,
        interface_layers=iface_layers,
        top_z_distance_mm=top_z,
        xy_distance_mm=0.35,
        reasons=reasons,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Brim
# ─────────────────────────────────────────────────────────────────────────────

def _decide_brim(f: GeometryFeatures, s: RiskScores) -> BrimDecision:
    reasons: list[str] = []
    bb  = f.bounding_box
    hbr = f.height_to_base_ratio

    needs_brim = (
        s.adhesion.value >= 25 or
        (f.contact_area_mm2 > 0 and f.contact_area_mm2 < 200) or
        hbr > 2.5 or
        max(bb.x_mm, bb.y_mm) > 150
    )

    if not needs_brim:
        return BrimDecision(
            enabled=False, width_mm=0.0,
            reasons=["Adhesion risk low — brim not needed"],
        )

    reasons.append(f"adhesion_risk={s.adhesion.value}")

    if s.adhesion.value >= 50:
        width = 8.0
        reasons.append("Wide brim 8mm: adhesion_risk >= 50")
    elif s.adhesion.value >= 25:
        width = 5.0
        reasons.append("Standard brim 5mm: adhesion_risk >= 25")
    else:
        width = 5.0
        reasons.append("Minimum brim 5mm: geometry risk (small contact area or tall model)")

    return BrimDecision(enabled=True, width_mm=width, reasons=reasons)


# ─────────────────────────────────────────────────────────────────────────────
# Layer height
# ─────────────────────────────────────────────────────────────────────────────

def _decide_layer(
    f: GeometryFeatures,
    s: RiskScores,
    base: float,
) -> LayerDecision:
    reasons: list[str] = []
    height = base

    if s.detail.value >= 60:
        height = min(height, 0.12)
        reasons.append(f"Fine layer 0.12mm: detail_risk={s.detail.value} >= 60")
    elif s.detail.value >= 30:
        height = min(height, 0.15)
        reasons.append(f"Medium layer 0.15mm: detail_risk={s.detail.value} >= 30")

    tw = f.thin_wall
    if tw.has_thin_walls and tw.min_thickness_mm < 2.0:
        height = min(height, 0.15)
        reasons.append(
            f"Layer cap 0.15mm: thin wall {tw.min_thickness_mm:.2f}mm < 2.0mm"
        )

    if not reasons:
        reasons.append(f"Base layer height {base}mm — no adjustment needed")

    return LayerDecision(height_mm=round(height, 3), reasons=reasons)


# ─────────────────────────────────────────────────────────────────────────────
# Walls
# ─────────────────────────────────────────────────────────────────────────────

def _decide_walls(
    f: GeometryFeatures,
    s: RiskScores,
    base_count:   int,
    base_top:     int,
    base_bottom:  int,
) -> WallDecision:
    reasons: list[str] = []
    count   = base_count
    top     = base_top
    bottom  = base_bottom

    if s.detail.value >= 60:
        count = max(count, 5)
        reasons.append(f"5 walls: detail_risk={s.detail.value} >= 60")
    elif s.detail.value >= 30:
        count = max(count, 4)
        reasons.append(f"4 walls: detail_risk={s.detail.value} >= 30")

    if s.stability.value >= 35:
        count = max(count, 4)
        reasons.append(f"4 walls: stability_risk={s.stability.value} >= 35")

    if s.difficulty == "hard":
        count   = max(count, 4)
        top     = max(top, 6)
        bottom  = max(bottom, 5)
        reasons.append("Extra shells: hard difficulty (max risk score >= 60)")
    elif s.difficulty == "moderate":
        count = max(count, 3)
        top   = max(top, 5)
        reasons.append("Extra top layers: moderate difficulty (max risk score >= 35)")

    if not reasons:
        reasons.append(f"Base wall count {base_count} — no adjustment needed")

    return WallDecision(
        count=count, top_layers=top, bottom_layers=bottom, reasons=reasons,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Infill
# ─────────────────────────────────────────────────────────────────────────────

def _decide_infill(
    f: GeometryFeatures,
    s: RiskScores,
    base: int,
) -> InfillDecision:
    reasons: list[str] = []
    percent = base

    if s.difficulty == "hard":
        percent = max(percent, 25)
        reasons.append(f"25% infill: hard difficulty (max risk={s.max_value})")
    elif s.difficulty == "moderate":
        percent = max(percent, 20)
        reasons.append(f"20% infill: moderate difficulty (max risk={s.max_value})")

    pattern, pat_reason = _select_infill_pattern(f, s)
    reasons.append(pat_reason)

    if not reasons:
        reasons.append(f"Base infill {base}% — no adjustment needed")

    return InfillDecision(percent=percent, pattern=pattern, reasons=reasons)


def _select_infill_pattern(
    f: GeometryFeatures,
    s: RiskScores,
) -> tuple[str, str]:
    """Returns (pattern_name, reason_string)."""

    if s.stability.value >= 50:
        return (
            "cubic",
            f"Cubic: structural model — strongest in all 3 axes (stability_risk={s.stability.value})",
        )

    if s.detail.value >= 30 and f.overhang.overhang_area_ratio > 0.05:
        return (
            "gyroid",
            f"Gyroid: organic/detailed geometry — isotropic, good surface finish "
            f"(detail_risk={s.detail.value}, overhang_ratio={f.overhang.overhang_area_ratio:.1%})",
        )

    if f.thin_wall.has_thin_walls and s.detail.value >= 15:
        return (
            "gyroid",
            f"Gyroid: thin-walled model — distributes stress evenly "
            f"(detail_risk={s.detail.value})",
        )

    return (
        "grid",
        f"Grid: standard balanced choice (stability_risk={s.stability.value}, "
        f"difficulty={s.difficulty!r})",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Speed and cooling
# ─────────────────────────────────────────────────────────────────────────────

def _decide_speed(
    f:          GeometryFeatures,
    s:          RiskScores,
    base_speed: int,
    base_fan:   int,
) -> SpeedDecision:
    reasons: list[str] = []
    speed          = base_speed
    fan            = base_fan
    min_layer_time = 8

    if s.stability.value >= 60:
        speed = min(speed, 60)
        reasons.append(f"Max 60mm/s: stability_risk={s.stability.value} >= 60")
    elif s.stability.value >= 35:
        speed = min(speed, 100)
        reasons.append(f"Max 100mm/s: stability_risk={s.stability.value} >= 35")

    # Bridge-specific cooling and speed — use bridge_risk for finer control
    if f.bridge.has_bridges:
        if f.bridge.max_span_mm > 3:
            fan = max(fan, 80)
            reasons.append(f"Fan >= 80%: bridge_span={f.bridge.max_span_mm:.1f}mm > 3mm")
        if f.bridge.max_span_mm > 8:
            fan = max(fan, 100)
            reasons.append(f"Fan 100%: bridge_span={f.bridge.max_span_mm:.1f}mm > 8mm")
        if s.bridge.value >= 35:
            speed = min(speed, 80)
            reasons.append(f"Max 80mm/s: bridge_risk={s.bridge.value} >= 35")
        if s.bridge.value >= 60:
            speed = min(speed, 50)
            reasons.append(f"Max 50mm/s: bridge_risk={s.bridge.value} >= 60 — long bridges")

    if s.detail.value >= 50:
        min_layer_time = max(min_layer_time, 15)
        reasons.append(f"Min layer time 15s: detail_risk={s.detail.value} >= 50")
    elif s.detail.value >= 30:
        min_layer_time = max(min_layer_time, 12)
        reasons.append(f"Min layer time 12s: detail_risk={s.detail.value} >= 30")

    if not reasons:
        reasons.append("Base speed — no geometry risk adjustments")

    return SpeedDecision(
        print_mm_s=speed,
        fan_percent=fan,
        min_layer_time_s=min_layer_time,
        reasons=reasons,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Quality: ironing, top surface, seam
# ─────────────────────────────────────────────────────────────────────────────

def _decide_quality(f: GeometryFeatures, s: RiskScores) -> QualityDecision:
    reasons: list[str] = []

    # Ironing — only useful on flat-top visual models
    ironing = False
    if s.detail.value >= 40 and not f.overhang.has_overhangs:
        ironing = True
        reasons.append(
            f"Ironing on: detail_risk={s.detail.value} >= 40, no overhangs (flat-top model)"
        )
    elif s.detail.value >= 25 and f.thin_wall.has_thin_walls:
        ironing = True
        reasons.append(f"Ironing on: fine detail + thin walls (detail_risk={s.detail.value})")

    # Top surface pattern
    top_surface: Literal["monotonic", "concentric"]
    if f.overhang.overhang_area_ratio > 0.10:
        top_surface = "concentric"
        reasons.append(
            f"Concentric top: organic shape "
            f"(overhang_ratio={f.overhang.overhang_area_ratio:.1%} > 10%)"
        )
    else:
        top_surface = "monotonic"
        reasons.append("Monotonic top: eliminates visible line seams (default for flat tops)")

    # Seam
    seam: Literal["aligned", "nearest"]
    if s.detail.value >= 20 or f.thin_wall.has_thin_walls:
        seam = "aligned"
        reasons.append("Aligned seam: visual/detailed model — seam hidden at back")
    elif s.stability.value >= 35:
        seam = "nearest"
        reasons.append(
            f"Nearest seam: structural model — minimise travel "
            f"(stability_risk={s.stability.value} >= 35)"
        )
    else:
        seam = "aligned"
        reasons.append("Aligned seam (default)")

    return QualityDecision(
        ironing_enabled=ironing,
        top_surface_pattern=top_surface,
        seam_position=seam,
        reasons=reasons,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Line width
# ─────────────────────────────────────────────────────────────────────────────

def _decide_line_width(
    f:         GeometryFeatures,
    s:         RiskScores,
    nozzle_mm: float = 0.4,
) -> LineWidthDecision:
    """
    Determine wall, first-layer, and infill line widths from nozzle size and
    geometry risk scores.

    Rules:
      - Thin walls or high detail risk → use exact nozzle diameter (100%)
        to maximise resolution; going wider would skip features < line_width.
      - Standard prints → 105% of nozzle for walls (slightly over-extruding
        fills gaps at corners), 125% first layer (better bed adhesion),
        110% infill (reduces gaps between infill lines, improves strength).
      - Printer constraint: line_width must be in [80%, 150%] of nozzle_mm.
    """
    reasons: list[str] = []
    tw = f.thin_wall

    # Constraint: clamp to safe range
    min_w = round(nozzle_mm * 0.80, 3)
    max_w = round(nozzle_mm * 1.50, 3)

    # Wall / perimeter width
    if tw.has_thin_walls and tw.min_thickness_mm < nozzle_mm * 2.5:
        # Thin walls: exact nozzle width maximises the chance of printing them
        wall_w = round(nozzle_mm, 3)
        reasons.append(
            f"Wall line width = exact nozzle {wall_w}mm — thin walls detected "
            f"({tw.min_thickness_mm:.2f}mm); going wider would skip features"
        )
    elif s.detail.value >= 40:
        wall_w = round(nozzle_mm, 3)
        reasons.append(
            f"Wall line width = exact nozzle {wall_w}mm — detail_risk={s.detail.value} "
            f"requires maximum resolution"
        )
    else:
        wall_w = round(min(nozzle_mm * 1.05, max_w), 3)
        reasons.append(
            f"Wall line width {wall_w}mm (105% of nozzle) — standard quality; "
            f"slight over-extrusion fills corner gaps without sacrificing detail"
        )

    # First-layer width: always wider to maximise bed adhesion
    first_w = round(min(nozzle_mm * 1.25, max_w), 3)
    reasons.append(
        f"First-layer line width {first_w}mm (125% of nozzle) — wider squish "
        f"maximises contact with the build plate"
    )

    # Infill width: 110% — infill is hidden so wider lines mean fewer passes
    infill_w = round(min(nozzle_mm * 1.10, max_w), 3)
    reasons.append(
        f"Infill line width {infill_w}mm (110% of nozzle) — infill is hidden; "
        f"slightly wider lines reduce gap count and improve part strength"
    )

    return LineWidthDecision(
        line_width_mm=wall_w,
        first_layer_width_mm=first_w,
        infill_width_mm=infill_w,
        reasons=reasons,
    )
