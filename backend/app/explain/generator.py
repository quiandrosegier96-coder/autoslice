"""
AutoSlice — Explanation generator.

generate_explanations(decisions, features, scores) → ExplanationReport

Translates the structured SettingsDecisions (which carry machine-readable reasons)
into plain-English sentences suitable for display to end users.

Pure function. No I/O. No side effects.
Works at analysis time — does not require a completed conversion.
"""

from __future__ import annotations

from app.explain.models import ExplanationReport, SettingExplanation
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


def generate_explanations(
    decisions: SettingsDecisions,
    features:  GeometryFeatures,
    scores:    RiskScores,
) -> ExplanationReport:
    """
    Build a full ExplanationReport from the three analysis artefacts.
    One SettingExplanation is produced per major setting domain.
    """
    items = [
        _explain_support(decisions.support, features, scores),
        _explain_brim(decisions.brim, features, scores),
        _explain_layer(decisions.layer, features, scores),
        _explain_line_width(decisions.line_width, features, scores),
        _explain_walls(decisions.walls, scores),
        _explain_infill(decisions.infill, scores),
        _explain_speed(decisions.speed, features, scores),
        _explain_quality(decisions.quality, features, scores),
    ]
    return ExplanationReport(
        summary=_generate_summary(decisions, scores),
        items=items,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Per-domain translators
# ─────────────────────────────────────────────────────────────────────────────

def _explain_support(
    d: SupportDecision,
    f: GeometryFeatures,
    s: RiskScores,
) -> SettingExplanation:
    if not d.enabled:
        return SettingExplanation(
            setting="Supports",
            value="Disabled",
            reason="No significant overhangs detected — the model can print cleanly without support material.",
            icon="check",
        )

    ov = f.overhang
    type_label = "Tree" if d.type == "tree" else "Normal"
    placement_label = "everywhere" if d.placement == "everywhere" else "build plate only"
    value = f"{type_label} supports, {d.density_percent}% density, {d.angle_threshold_deg}° threshold, {placement_label}"

    if d.type == "tree":
        reason = (
            f"Tree supports selected because {ov.overhang_area_ratio:.0%} of the model surface has steep "
            f"overhangs (max {ov.max_angle_deg:.0f}°). Tree supports handle organic shapes better and "
            f"are easier to remove than normal supports."
        )
    else:
        triggered_pct = ov.moderate_area_ratio + ov.severe_area_ratio
        reason = (
            f"Supports enabled because {triggered_pct:.0%} of downward-facing surfaces exceed "
            f"the {d.angle_threshold_deg}° overhang threshold. Normal grid supports are sufficient "
            f"for this geometry."
        )

    if d.placement == "everywhere":
        reason += (
            " Placement set to everywhere — overhangs are distributed across the model "
            "and not all are reachable from the build plate."
        )
    else:
        reason += " Placement: build plate only — simpler geometry, less material, easier removal."

    return SettingExplanation(setting="Supports", value=value, reason=reason, icon="warning")


def _explain_brim(
    d: BrimDecision,
    f: GeometryFeatures,
    s: RiskScores,
) -> SettingExplanation:
    if not d.enabled:
        contact_note = (
            f" (contact area {f.contact_area_mm2:.0f} mm²)"
            if f.contact_area_mm2 > 0 else ""
        )
        return SettingExplanation(
            setting="Brim",
            value="Disabled",
            reason=f"Bed contact area is sufficient{contact_note} — no brim needed to hold the model down.",
            icon="check",
        )

    reasons: list[str] = []
    if f.contact_area_mm2 > 0 and f.contact_area_mm2 < 200:
        reasons.append(f"small contact footprint ({f.contact_area_mm2:.0f} mm²)")
    if f.height_to_base_ratio > 2.5:
        reasons.append(f"tall relative to its base ({f.height_to_base_ratio:.1f}× height-to-base ratio)")
    if s.adhesion.value >= 50:
        reasons.append("high overall adhesion risk")
    if not reasons:
        reasons.append("geometry requires additional bed adhesion")

    reason_str = ", ".join(reasons[:-1]) + (" and " + reasons[-1] if len(reasons) > 1 else reasons[0])
    return SettingExplanation(
        setting="Brim",
        value=f"{d.width_mm:.0f} mm wide",
        reason=f"Brim added ({d.width_mm:.0f} mm) because the model has {reason_str}.",
        icon="warning" if s.adhesion.value >= 50 else "info",
    )


def _explain_layer(
    d: LayerDecision,
    f: GeometryFeatures,
    s: RiskScores,
) -> SettingExplanation:
    tw = f.thin_wall
    if s.detail.value < 30 and not (tw.has_thin_walls and tw.min_thickness_mm < 2.0):
        return SettingExplanation(
            setting="Layer Height",
            value=f"{d.height_mm:.2f} mm",
            reason=(
                f"Standard layer height {d.height_mm:.2f} mm — no thin features require "
                f"a finer resolution."
            ),
            icon="check",
        )

    reasons: list[str] = []
    if s.detail.value >= 60:
        reasons.append("very fine surface detail detected")
    elif s.detail.value >= 30:
        reasons.append("detailed geometry detected")
    if tw.has_thin_walls and tw.min_thickness_mm < 2.0:
        reasons.append(
            f"thin walls as narrow as {tw.min_thickness_mm:.2f} mm require finer layers "
            f"to be printed reliably"
        )

    reason_str = "; ".join(reasons)
    return SettingExplanation(
        setting="Layer Height",
        value=f"{d.height_mm:.2f} mm",
        reason=f"Layer height reduced to {d.height_mm:.2f} mm because {reason_str}.",
        icon="info",
    )


def _explain_line_width(
    d: LineWidthDecision,
    f: GeometryFeatures,
    s: RiskScores,
) -> SettingExplanation:
    tw = f.thin_wall
    value = f"{d.line_width_mm}mm walls / {d.first_layer_width_mm}mm first layer / {d.infill_width_mm}mm infill"

    if tw.has_thin_walls and tw.min_thickness_mm < d.line_width_mm * 2.5:
        reason = (
            f"Line width set to exact nozzle diameter ({d.line_width_mm}mm) because thin walls "
            f"({tw.min_thickness_mm:.2f}mm) are close to the nozzle limit. A wider line would "
            f"skip these features entirely. First layer is {d.first_layer_width_mm}mm for adhesion."
        )
        icon = "warning"
    elif s.detail.value >= 40:
        reason = (
            f"Line width kept at exact nozzle size ({d.line_width_mm}mm) for maximum resolution "
            f"on a detail-sensitive model (detail risk {s.detail.value}/100). "
            f"Infill uses {d.infill_width_mm}mm (slightly wider, hidden inside)."
        )
        icon = "info"
    else:
        reason = (
            f"Standard line widths: walls {d.line_width_mm}mm (105% of nozzle), "
            f"first layer {d.first_layer_width_mm}mm (125% for bed grip), "
            f"infill {d.infill_width_mm}mm (110% for fewer passes and better part strength)."
        )
        icon = "check"

    return SettingExplanation(setting="Line Widths", value=value, reason=reason, icon=icon)


def _explain_walls(d: WallDecision, s: RiskScores) -> SettingExplanation:
    value = f"{d.count} walls, {d.top_layers} top layers, {d.bottom_layers} bottom layers"
    reasons: list[str] = []

    if s.detail.value >= 60:
        reasons.append(
            f"high detail risk ({s.detail.value}/100) — more perimeters improve fine feature accuracy"
        )
    elif s.detail.value >= 30:
        reasons.append("detailed geometry benefits from extra perimeter shells")

    if s.stability.value >= 35:
        reasons.append(
            f"stability risk {s.stability.value}/100 — extra walls reinforce the structure"
        )

    if s.difficulty == "hard":
        reasons.append("maximum wall count applied for a challenging model")

    if not reasons:
        return SettingExplanation(
            setting="Walls",
            value=value,
            reason=f"Standard wall count ({d.count}) — geometry does not require extra reinforcement.",
            icon="check",
        )

    reason_str = "; ".join(reasons)
    return SettingExplanation(
        setting="Walls",
        value=value,
        reason=f"Wall count increased to {d.count} because {reason_str}.",
        icon="info",
    )


def _explain_infill(d: InfillDecision, s: RiskScores) -> SettingExplanation:
    _pattern_descriptions: dict[str, str] = {
        "cubic":  "cubic (strongest in all 3 axes, chosen for structural models)",
        "gyroid": "gyroid (isotropic stress distribution, chosen for organic or thin-walled geometry)",
        "grid":   "grid (balanced default for general-purpose prints)",
    }
    pattern_label = _pattern_descriptions.get(d.pattern, d.pattern)
    value = f"{d.percent}% {d.pattern}"

    if s.difficulty == "hard":
        return SettingExplanation(
            setting="Infill",
            value=value,
            reason=(
                f"Infill raised to {d.percent}% because this is a challenging model "
                f"(overall risk {s.max_value}/100). Pattern: {pattern_label}."
            ),
            icon="warning",
        )
    if s.difficulty == "moderate":
        return SettingExplanation(
            setting="Infill",
            value=value,
            reason=(
                f"Infill set to {d.percent}% for moderate complexity. "
                f"Pattern: {pattern_label}."
            ),
            icon="info",
        )
    return SettingExplanation(
        setting="Infill",
        value=value,
        reason=f"Standard {d.percent}% infill — no structural demands detected. Pattern: {pattern_label}.",
        icon="check",
    )


def _explain_speed(
    d: SpeedDecision,
    f: GeometryFeatures,
    s: RiskScores,
) -> SettingExplanation:
    value = f"{d.print_mm_s} mm/s, fan {d.fan_percent}%, min {d.min_layer_time_s}s/layer"
    adjustments: list[str] = []

    if s.stability.value >= 60:
        adjustments.append(
            f"speed limited to {d.print_mm_s} mm/s to prevent vibration knocking over a tall, "
            f"narrow model (stability risk {s.stability.value}/100)"
        )
    elif s.stability.value >= 35:
        adjustments.append(
            f"speed reduced to {d.print_mm_s} mm/s for a model with elevated stability risk"
        )

    if f.bridge.has_bridges and f.bridge.max_span_mm > 8:
        adjustments.append(
            f"fan at {d.fan_percent}% to solidify bridging ({f.bridge.max_span_mm:.0f} mm span)"
        )

    if d.min_layer_time_s > 8:
        adjustments.append(
            f"minimum {d.min_layer_time_s}s per layer to allow proper cooling on small cross-sections"
        )

    if not adjustments:
        return SettingExplanation(
            setting="Speed & Cooling",
            value=value,
            reason="Full print speed — no geometry constraints require adjustment.",
            icon="check",
        )

    reason_str = "; ".join(adjustments)
    return SettingExplanation(
        setting="Speed & Cooling",
        value=value,
        reason=f"Speed/cooling adjusted: {reason_str}.",
        icon="info",
    )


def _explain_quality(
    d: QualityDecision,
    f: GeometryFeatures,
    s: RiskScores,
) -> SettingExplanation:
    parts: list[str] = []
    if d.ironing_enabled:
        parts.append("ironing on")
    parts.append(f"{d.top_surface_pattern} top fill")
    parts.append(f"{d.seam_position} seam")
    value = ", ".join(parts)

    if d.ironing_enabled:
        reason = (
            f"Ironing enabled to smooth the top surface on a detail-sensitive model "
            f"(detail risk {s.detail.value}/100). "
            f"{d.top_surface_pattern.capitalize()} fill minimises visible layer lines."
        )
    elif d.top_surface_pattern == "concentric":
        reason = (
            f"Concentric top fill chosen for organic geometry "
            f"({f.overhang.overhang_area_ratio:.0%} overhang ratio) — follows the model contour "
            f"better than a straight monotonic pattern."
        )
    else:
        reason = (
            "Monotonic top fill for clean, gap-free surface finish. "
            f"{d.seam_position.capitalize()} seam to minimise visibility."
        )

    return SettingExplanation(setting="Surface Quality", value=value, reason=reason, icon="info")


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

def _generate_summary(decisions: SettingsDecisions, scores: RiskScores) -> str:
    risk_labels: list[str] = []
    if scores.support.value >= 35:
        risk_labels.append("overhangs")
    if scores.adhesion.value >= 35:
        risk_labels.append("bed adhesion")
    if scores.stability.value >= 35:
        risk_labels.append("structural stability")
    if scores.detail.value >= 35:
        risk_labels.append("fine detail")

    if not risk_labels:
        return (
            "Straightforward model — settings use well-balanced defaults "
            "optimised for clean results with no special accommodations needed."
        )

    risk_str = (
        ", ".join(risk_labels[:-1]) + " and " + risk_labels[-1]
        if len(risk_labels) > 1 else risk_labels[0]
    )

    if scores.difficulty == "hard":
        return (
            f"Challenging model with significant {risk_str} concerns — settings have been "
            f"adjusted to prioritise print success over speed."
        )
    if scores.difficulty == "moderate":
        return (
            f"Moderate complexity detected ({risk_str}) — targeted adjustments applied "
            f"to ensure reliable results."
        )
    return (
        f"Minor {risk_str} considerations detected — small settings adjustments applied."
    )
