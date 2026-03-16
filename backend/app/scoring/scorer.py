"""
AutoSlice — Rule-based risk scorer.

compute_risk_scores(features) → RiskScores

Pure functions. No side effects. No I/O.
Each _score_* function returns a RiskScore with a numeric value (0–100),
a level enum, and an ordered list of reasons for that score — one reason
per threshold crossed.

Improvements over v1:
  - Overhang scoring uses 3 severity zones (mild/moderate/severe) for finer control.
  - Bridge risk is a separate category, not folded into support risk.
  - Stability scoring factors in slenderness_ratio and center_of_mass_z_ratio.
  - Adhesion scoring uses slenderness_ratio as an additional signal.
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
        bridge    = _score_bridge(features),
        adhesion  = _score_adhesion(features),
        stability = _score_stability(features),
        detail    = _score_detail(features),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Support risk
# Measures how much unsupported overhang geometry exists.
# Uses 3-tier overhang severity zones for more nuanced scoring.
# ─────────────────────────────────────────────────────────────────────────────

def _score_support(f: GeometryFeatures) -> RiskScore:
    value = 0
    reasons: list[str] = []

    ov = f.overhang

    # Tier 1: mild overhangs (45–55°) — printable but borderline
    if ov.mild_area_ratio > 0.10:
        value += 10
        reasons.append(
            f"Mild overhang zone (45–55°) covers {ov.mild_area_ratio:.1%} of surface"
        )

    # Tier 2: moderate overhangs (55–65°) — likely need support
    if ov.moderate_area_ratio > 0.02:
        value += 20
        reasons.append(
            f"Moderate overhang zone (55–65°) covers {ov.moderate_area_ratio:.1%} — support likely needed"
        )
    if ov.moderate_area_ratio > 0.08:
        value += 10
        reasons.append(
            "Moderate overhang zone exceeds 8% of surface — significant unsupported geometry"
        )

    # Tier 3: severe overhangs (65°+) — always need support
    if ov.severe_area_ratio > 0.005:
        value += 25
        reasons.append(
            f"Severe overhang zone (65°+) covers {ov.severe_area_ratio:.1%} — support required"
        )
    if ov.severe_area_ratio > 0.05:
        value += 15
        reasons.append(
            "Severe overhang zone exceeds 5% — heavy support coverage needed"
        )

    # Worst-case angle still matters as a signal
    if ov.max_angle_deg > 70:
        value += 10
        reasons.append(
            f"Max overhang angle {ov.max_angle_deg:.1f}° > 70° — near-flat underside"
        )

    # Large absolute support area adds material risk
    if ov.estimated_support_area_mm2 > 500:
        value += 5
        reasons.append(
            f"Estimated support footprint {ov.estimated_support_area_mm2:.0f}mm² — heavy support material"
        )

    value = min(100, value)
    if not reasons:
        reasons.append("No significant overhangs detected")

    return RiskScore(value=value, level=risk_level(value), reasons=reasons)


# ─────────────────────────────────────────────────────────────────────────────
# Bridge risk
# Measures bridge quality risk: long unsupported spans degrade surface finish
# and may sag. Separate from support risk because bridges are printed
# without supports — the risk is print quality, not failure to slice.
# ─────────────────────────────────────────────────────────────────────────────

def _score_bridge(f: GeometryFeatures) -> RiskScore:
    value = 0
    reasons: list[str] = []

    br = f.bridge

    if not br.has_bridges:
        return RiskScore(value=0, level=risk_level(0),
                         reasons=["No bridge regions detected"])

    reasons.append(f"{br.cluster_count} bridge region(s) detected")

    if br.max_span_mm > 5:
        value += 15
        reasons.append(f"Bridge span {br.max_span_mm:.1f}mm > 5mm — cooling critical")

    if br.max_span_mm > 15:
        value += 20
        reasons.append(f"Bridge span {br.max_span_mm:.1f}mm > 15mm — surface sag risk")

    if br.max_span_mm > 30:
        value += 20
        reasons.append(f"Bridge span {br.max_span_mm:.1f}mm > 30mm — support recommended")

    if br.cluster_count >= 3:
        value += 10
        reasons.append(f"{br.cluster_count} separate bridge regions — complex geometry")

    if br.bridge_area_mm2 > 200:
        value += 10
        reasons.append(f"Bridge area {br.bridge_area_mm2:.0f}mm² — large unsupported surface")

    value = min(100, value)
    return RiskScore(value=value, level=risk_level(value), reasons=reasons)


# ─────────────────────────────────────────────────────────────────────────────
# Adhesion risk
# Measures how likely the part is to detach from the bed mid-print.
# Driven by contact area, height-to-base ratio, slenderness, and footprint size.
# ─────────────────────────────────────────────────────────────────────────────

def _score_adhesion(f: GeometryFeatures) -> RiskScore:
    value = 0
    reasons: list[str] = []

    bb  = f.bounding_box
    hbr = f.height_to_base_ratio

    if f.contact_area_mm2 > 0:
        if f.contact_area_mm2 < 50:
            value += 50
            reasons.append(
                f"Tiny contact area {f.contact_area_mm2:.0f}mm² < 50mm² — very poor bed grip"
            )
        elif f.contact_area_mm2 < 100:
            value += 35
            reasons.append(
                f"Very small contact area {f.contact_area_mm2:.0f}mm² < 100mm² — minimal bed grip"
            )
        elif f.contact_area_mm2 < 300:
            value += 15
            reasons.append(
                f"Small contact area {f.contact_area_mm2:.0f}mm² < 300mm²"
            )

    if hbr > 2.5:
        value += 15
        reasons.append(f"Height-to-base ratio {hbr:.2f} > 2.5 — tall relative to footprint")

    if hbr > 4.0:
        value += 15
        reasons.append(f"Height-to-base ratio {hbr:.2f} > 4.0 — very tall, high tip-over risk")

    # Slenderness ratio as secondary stability signal
    if f.slenderness_ratio > 4.0:
        value += 10
        reasons.append(f"Slenderness ratio {f.slenderness_ratio:.1f} > 4 — tall narrow model")

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
# Primary signal: height-to-base ratio. Secondary: slenderness + center of mass.
# ─────────────────────────────────────────────────────────────────────────────

def _score_stability(f: GeometryFeatures) -> RiskScore:
    value = 0
    reasons: list[str] = []

    hbr = f.height_to_base_ratio
    bb  = f.bounding_box
    com = f.center_of_mass_z_ratio
    sl  = f.slenderness_ratio

    if hbr > 0:
        if hbr > 3.5:
            value += 30
            reasons.append(f"Height-to-base ratio {hbr:.2f} > 3.5 — unstable geometry")
        if hbr > 5.0:
            value += 20
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

    # Slenderness ratio amplifies stability risk for combined tall+narrow models
    if sl > 3.0 and hbr > 2.0:
        value += 10
        reasons.append(f"Slenderness {sl:.1f} combined with HBR {hbr:.2f} — compounding risk")

    # Top-heavy center of mass
    if com > 0.65:
        value += 15
        reasons.append(
            f"Center of mass at {com:.0%} of height — top-heavy, tip-over risk amplified"
        )
    elif com > 0.55:
        value += 5
        reasons.append(f"Center of mass slightly above midpoint ({com:.0%})")

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
        value += 35
        reasons.append("Thin walls detected — features near nozzle width limit")

    if tw.min_thickness_mm < 0.8:
        value += 35
        reasons.append(
            f"Minimum wall thickness {tw.min_thickness_mm:.2f}mm < 0.8mm — below nozzle diameter"
        )
    elif tw.min_thickness_mm < 1.2:
        value += 25
        reasons.append(
            f"Minimum wall thickness {tw.min_thickness_mm:.2f}mm < 1.2mm — sub-nozzle risk"
        )
    elif tw.min_thickness_mm < 2.0:
        value += 10
        reasons.append(
            f"Minimum wall thickness {tw.min_thickness_mm:.2f}mm < 2.0mm — marginal"
        )

    if 0 < bb.z_mm < 3.0:
        value += 20
        reasons.append(
            f"Very low model height {bb.z_mm:.1f}mm — fine detail captured in few layers"
        )

    value = min(100, value)
    if not reasons:
        reasons.append("No thin walls or fine features detected")

    return RiskScore(value=value, level=risk_level(value), reasons=reasons)
