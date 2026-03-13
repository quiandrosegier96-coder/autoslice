"""
AutoSlice — Rule-based risk scorer.

compute_risk_scores(features) → RiskScores

Pure functions. No side effects. No I/O.
Each _score_* function returns a RiskScore with a numeric value (0–100),
a level enum, and an ordered list of reasons for that score — one reason
per threshold crossed.
"""

from app.scoring.models import (
    GeometryFeatures,
    RiskLevel,
    RiskScore,
    RiskScores,
    risk_level,
)


def compute_risk_scores(features: GeometryFeatures) -> RiskScores:
    return RiskScores(
        support   = _score_support(features),
        adhesion  = _score_adhesion(features),
        stability = _score_stability(features),
        detail    = _score_detail(features),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Support risk
# Measures how much unsupported geometry exists and how likely it is to fail.
# ─────────────────────────────────────────────────────────────────────────────

def _score_support(f: GeometryFeatures) -> RiskScore:
    value = 0
    reasons: list[str] = []

    ov = f.overhang

    if ov.max_angle_deg > 45:
        value += 25
        reasons.append(f"Overhang angle {ov.max_angle_deg:.1f}° > 45°")

    if ov.max_angle_deg > 60:
        value += 20
        reasons.append(f"Overhang angle {ov.max_angle_deg:.1f}° > 60° — steep unsupported face")

    if ov.overhang_area_ratio > 0.05:
        value += 20
        reasons.append(f"Overhang area ratio {ov.overhang_area_ratio:.1%} > 5% of surface")

    if ov.overhang_area_ratio > 0.15:
        value += 15
        reasons.append(f"Overhang area ratio {ov.overhang_area_ratio:.1%} > 15% — extensive overhang")

    if f.bridge.max_span_mm > 10:
        value += 10
        reasons.append(f"Bridge span {f.bridge.max_span_mm:.1f}mm > 10mm")

    if f.bridge.max_span_mm > 20:
        value += 10
        reasons.append(f"Bridge span {f.bridge.max_span_mm:.1f}mm > 20mm — long unsupported bridge")

    value = min(100, value)
    if not reasons:
        reasons.append("No significant overhangs or bridges detected")

    return RiskScore(value=value, level=risk_level(value), reasons=reasons)


# ─────────────────────────────────────────────────────────────────────────────
# Adhesion risk
# Measures how likely the part is to detach from the bed mid-print.
# Driven by contact area, height-to-base ratio, and footprint size.
# ─────────────────────────────────────────────────────────────────────────────

def _score_adhesion(f: GeometryFeatures) -> RiskScore:
    value = 0
    reasons: list[str] = []

    bb  = f.bounding_box
    hbr = f.height_to_base_ratio

    if f.contact_area_mm2 > 0:
        if f.contact_area_mm2 < 100:
            value += 40
            reasons.append(
                f"Very small contact area {f.contact_area_mm2:.0f}mm² < 100mm² — minimal bed grip"
            )
        elif f.contact_area_mm2 < 300:
            value += 20
            reasons.append(
                f"Small contact area {f.contact_area_mm2:.0f}mm² < 300mm²"
            )

    if hbr > 2.5:
        value += 20
        reasons.append(f"Height-to-base ratio {hbr:.2f} > 2.5 — tall relative to footprint")

    if hbr > 4.0:
        value += 15
        reasons.append(f"Height-to-base ratio {hbr:.2f} > 4.0 — very tall, high tip-over risk")

    if max(bb.x_mm, bb.y_mm) > 150:
        value += 10
        reasons.append(
            f"Large footprint {max(bb.x_mm, bb.y_mm):.0f}mm — corner warping risk on large beds"
        )

    value = min(100, value)
    if not reasons:
        reasons.append("Contact area and height-to-base ratio within safe range")

    return RiskScore(value=value, level=risk_level(value), reasons=reasons)


# ─────────────────────────────────────────────────────────────────────────────
# Stability risk
# Measures how likely the part is to shift or collapse during printing.
# Primary signal is height-to-base ratio (HBR). Fallback: bounding box ratio.
# ─────────────────────────────────────────────────────────────────────────────

def _score_stability(f: GeometryFeatures) -> RiskScore:
    value = 0
    reasons: list[str] = []

    hbr = f.height_to_base_ratio
    bb  = f.bounding_box

    if hbr > 0:
        if hbr > 3.5:
            value += 35
            reasons.append(f"Height-to-base ratio {hbr:.2f} > 3.5 — unstable geometry")
        if hbr > 5.0:
            value += 25
            reasons.append(f"Height-to-base ratio {hbr:.2f} > 5.0 — highly unstable")
        if hbr > 7.0:
            value += 20
            reasons.append(f"Height-to-base ratio {hbr:.2f} > 7.0 — extreme instability risk")
    else:
        # HBR unavailable — fall back to raw bounding box aspect ratio
        base_min = min(bb.x_mm, bb.y_mm)
        if base_min > 0:
            aspect = bb.z_mm / base_min
            if aspect > 4.0:
                value += 40
                reasons.append(
                    f"Aspect ratio Z/min_XY = {aspect:.1f} > 4.0 — tall and narrow"
                )

    value = min(100, value)
    if not reasons:
        reasons.append("Height-to-base ratio within stable range")

    return RiskScore(value=value, level=risk_level(value), reasons=reasons)


# ─────────────────────────────────────────────────────────────────────────────
# Detail risk
# Measures how likely fine features are to be lost or degraded.
# Driven by thin walls and very low model height.
# ─────────────────────────────────────────────────────────────────────────────

def _score_detail(f: GeometryFeatures) -> RiskScore:
    value = 0
    reasons: list[str] = []

    tw = f.thin_wall
    bb = f.bounding_box

    if tw.has_thin_walls:
        value += 40
        reasons.append("Thin walls detected — features near nozzle width limit")

    if tw.min_thickness_mm < 1.2:
        value += 30
        reasons.append(
            f"Minimum wall thickness {tw.min_thickness_mm:.2f}mm < 1.2mm — sub-nozzle risk"
        )
    elif tw.min_thickness_mm < 2.0:
        value += 15
        reasons.append(
            f"Minimum wall thickness {tw.min_thickness_mm:.2f}mm < 2.0mm — marginal"
        )

    if 0 < bb.z_mm < 3.0:
        value += 20
        reasons.append(
            f"Very low model height {bb.z_mm:.1f}mm — fine detail in few layers"
        )

    value = min(100, value)
    if not reasons:
        reasons.append("No thin walls or fine features detected")

    return RiskScore(value=value, level=risk_level(value), reasons=reasons)
