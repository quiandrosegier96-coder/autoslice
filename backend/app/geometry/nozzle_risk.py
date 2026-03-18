"""
AutoSlice — Nozzle collision risk analyser.

Estimates the risk of the printer nozzle scraping or colliding with the
print during travel moves, based on geometry features derived from the mesh.

Because we do not have actual slicer travel paths (no G-code yet at this
stage), all risks are derived from geometry heuristics.  Each risk is
assigned a severity so the UI can prioritise warnings and suggest fixes.

Risk types
──────────
overhang_curl
    Steep overhangs whose corners tend to curl upward during printing.
    The curled edge can be struck by the nozzle on the next travel move.

bridge_droop
    Long unsupported bridges that sag below the intended plane.
    A sagging bridge raises the effective surface height, causing the
    nozzle to scrape it on the next pass.

tower_sway
    Tall, slender features that flex during printing.  A swaying tower
    can move into the nozzle path on travel moves.

travel_scrape
    General travel-path scraping risk from concave / re-entrant geometry
    or thin walls where the nozzle must pass close to existing extrusions.

Recommended fixes (returned with the report)
────────────────────────────────────────────
- Z-hop:   lift the nozzle by 0.2–0.6 mm before travel moves
- Combing: keep travels inside the perimeter to avoid crossing open air
- Flow:    reduce 2–5% to avoid over-extrusion blobs that raise surface height
- Cooling: increase to reduce curl on steep overhangs
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import trimesh


# ── Thresholds ────────────────────────────────────────────────────────────────

_CURL_OVERHANG_RATIO   = 0.08   # ≥8 % overhang area → curl risk
_SEVERE_OVERHANG_RATIO = 0.04   # ≥4 % severe (>65°) → high curl risk
_BRIDGE_DROOP_MM       = 8.0    # bridge span ≥ 8 mm → droop risk
_BRIDGE_DROOP_HIGH_MM  = 15.0   # span ≥ 15 mm → high droop risk
_TOWER_SWAY_RATIO      = 3.5    # height/base ≥ 3.5 → sway risk
_TOWER_SWAY_HIGH_RATIO = 6.0    # height/base ≥ 6.0 → high sway risk
_THIN_WALL_MM          = 0.8    # thin wall ≤ 0.8 mm → travel scrape risk


# ── Data models ───────────────────────────────────────────────────────────────

Severity = Literal["low", "medium", "high"]


@dataclass
class NozzleRisk:
    type:           str        # one of the four risk types above
    severity:       Severity
    reason:         str        # plain-language description
    recommendation: str        # specific fix to apply


@dataclass
class NozzleRiskReport:
    has_risks:            bool
    risks:                list[NozzleRisk] = field(default_factory=list)

    # Aggregated fix recommendations derived from all detected risks
    recommended_z_hop_mm: float = 0.0    # 0 = no z-hop needed
    recommended_combing:  str   = "off"  # "off" | "not_in_skin" | "all"
    recommended_flow_pct: float = 100.0  # nominal flow percentage


# ── Public entry point ────────────────────────────────────────────────────────

def assess_nozzle_risk(
    overhang_area_ratio:  float = 0.0,
    severe_overhang_ratio: float = 0.0,
    bridge_max_span_mm:   float = 0.0,
    height_to_base_ratio: float = 0.0,
    min_wall_mm:          float = 999.0,
    has_thin_walls:       bool  = False,
) -> NozzleRiskReport:
    """
    Assess nozzle collision risk from pre-computed geometry metrics.

    Parameters
    ----------
    overhang_area_ratio : float
        Fraction of surface that overhangs (0–1).
    severe_overhang_ratio : float
        Fraction of surface with overhangs > 65° (0–1).
    bridge_max_span_mm : float
        Longest unsupported bridge span in mm.
    height_to_base_ratio : float
        Model height divided by its contact footprint.
    min_wall_mm : float
        Thinnest detected wall in mm.
    has_thin_walls : bool
        Whether the model contains walls thinner than a typical nozzle.

    Returns
    -------
    NozzleRiskReport
    """
    risks: list[NozzleRisk] = []

    # ── 1. Overhang curl ──────────────────────────────────────────────────────
    if severe_overhang_ratio >= _SEVERE_OVERHANG_RATIO:
        risks.append(NozzleRisk(
            type="overhang_curl",
            severity="high",
            reason=(
                f"Severe overhangs cover {severe_overhang_ratio * 100:.1f}% of the surface. "
                "Corners curl upward during printing and can be struck by the nozzle."
            ),
            recommendation=(
                "Enable Z-hop (0.4–0.6 mm), increase cooling fan to ≥70%, "
                "and reduce overhang print speed to 20–25 mm/s."
            ),
        ))
    elif overhang_area_ratio >= _CURL_OVERHANG_RATIO:
        risks.append(NozzleRisk(
            type="overhang_curl",
            severity="medium",
            reason=(
                f"Overhangs cover {overhang_area_ratio * 100:.1f}% of the surface. "
                "Moderate curl risk on unsupported edges."
            ),
            recommendation=(
                "Enable Z-hop (0.2–0.4 mm) and set combing to 'Not in Skin' "
                "to prevent travel moves crossing open overhang areas."
            ),
        ))

    # ── 2. Bridge droop ───────────────────────────────────────────────────────
    if bridge_max_span_mm >= _BRIDGE_DROOP_HIGH_MM:
        risks.append(NozzleRisk(
            type="bridge_droop",
            severity="high",
            reason=(
                f"Bridge span of {bridge_max_span_mm:.1f} mm is likely to sag. "
                "The drooped surface raises the effective height, causing the nozzle "
                "to scrape it on the next travel."
            ),
            recommendation=(
                "Reduce flow to 90–95% on bridge layers, maximise cooling fan speed, "
                "and enable Z-hop (0.4 mm) on travel moves."
            ),
        ))
    elif bridge_max_span_mm >= _BRIDGE_DROOP_MM:
        risks.append(NozzleRisk(
            type="bridge_droop",
            severity="medium",
            reason=(
                f"Bridge span of {bridge_max_span_mm:.1f} mm may sag slightly under gravity. "
                "Nozzle scraping risk on subsequent layers."
            ),
            recommendation=(
                "Set bridge flow to 95%, enable high cooling on bridges, "
                "and use Z-hop (0.2 mm) during travel."
            ),
        ))

    # ── 3. Tower sway ─────────────────────────────────────────────────────────
    if height_to_base_ratio >= _TOWER_SWAY_HIGH_RATIO:
        risks.append(NozzleRisk(
            type="tower_sway",
            severity="high",
            reason=(
                f"Height-to-base ratio of {height_to_base_ratio:.1f} is very high. "
                "Slender features flex during rapid moves, shifting into the nozzle path."
            ),
            recommendation=(
                "Reduce print speed to 30–40 mm/s, enable Z-hop (0.4 mm), "
                "consider printing with a brim, and use 'Print one at a time' if multiple parts."
            ),
        ))
    elif height_to_base_ratio >= _TOWER_SWAY_RATIO:
        risks.append(NozzleRisk(
            type="tower_sway",
            severity="medium",
            reason=(
                f"Height-to-base ratio of {height_to_base_ratio:.1f} indicates a moderately "
                "slender model that may vibrate during fast moves."
            ),
            recommendation=(
                "Reduce travel speed to 120 mm/s or less and enable Z-hop (0.2 mm)."
            ),
        ))

    # ── 4. Travel scrape (thin walls) ─────────────────────────────────────────
    if has_thin_walls and min_wall_mm <= _THIN_WALL_MM:
        risks.append(NozzleRisk(
            type="travel_scrape",
            severity="medium",
            reason=(
                f"Walls as thin as {min_wall_mm:.1f} mm exist. "
                "The nozzle passes very close to adjacent extrusions, "
                "increasing the chance of scraping or knocking them loose."
            ),
            recommendation=(
                "Enable combing ('Not in Skin') to keep travel moves inside "
                "the part perimeter, and reduce travel speed near thin sections."
            ),
        ))

    if not risks:
        return NozzleRiskReport(has_risks=False)

    # ── Aggregate recommended settings ────────────────────────────────────────
    max_severity = (
        "high"   if any(r.severity == "high"   for r in risks) else
        "medium" if any(r.severity == "medium" for r in risks) else "low"
    )

    z_hop_mm = (
        0.4 if max_severity == "high"   else
        0.2 if max_severity == "medium" else 0.0
    )

    combing = "not_in_skin"   # always safer than off when risks exist

    flow_pct = (
        95.0 if max_severity == "high"   else
        98.0 if max_severity == "medium" else 100.0
    )

    return NozzleRiskReport(
        has_risks=True,
        risks=risks,
        recommended_z_hop_mm=z_hop_mm,
        recommended_combing=combing,
        recommended_flow_pct=flow_pct,
    )
