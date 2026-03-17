"""
AutoSlice — Printability scoring.

compute_printability(support_risk, adhesion_risk, stability_risk, detail_risk, bridge_risk)
  → PrintabilityScore

Input risk values are 0–100 (higher = more problematic).
Output total is 0–100 (higher = more printable / easier).

Sub-scores are the direct inversion of the corresponding risk dimension.
The weighted total reflects how often each failure mode causes real print problems
in practice: support failures are most common, then adhesion, then stability.

Weights:
  support   30%
  adhesion  25%
  stability 20%
  detail    15%
  bridge    10%
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PrintabilityScore(BaseModel):
    total:            int = Field(ge=0, le=100)   # overall score, higher = easier to print
    support_score:    int = Field(ge=0, le=100)   # 100 - support_risk
    adhesion_score:   int = Field(ge=0, le=100)   # 100 - adhesion_risk
    stability_score:  int = Field(ge=0, le=100)   # 100 - stability_risk
    detail_score:     int = Field(ge=0, le=100)   # 100 - detail_risk
    bridge_score:     int = Field(ge=0, le=100)   # 100 - bridge_risk
    difficulty_label: str                          # "Easy" | "Moderate" | "Challenging" | "Expert"
    warnings:         list[str]                    # actionable user-facing messages


def compute_printability(
    support_risk:   int,
    adhesion_risk:  int,
    stability_risk: int,
    detail_risk:    int,
    bridge_risk:    int = 0,
) -> PrintabilityScore:
    """
    Compute a printability score from the five risk dimensions.
    All inputs are clamped to 0–100 internally.
    """
    # Clamp inputs defensively
    sr  = max(0, min(100, support_risk))
    ar  = max(0, min(100, adhesion_risk))
    str_ = max(0, min(100, stability_risk))
    dr  = max(0, min(100, detail_risk))
    br  = max(0, min(100, bridge_risk))

    # Invert: how printable is each dimension?
    support_score   = 100 - sr
    adhesion_score  = 100 - ar
    stability_score = 100 - str_
    detail_score    = 100 - dr
    bridge_score    = 100 - br

    # Weighted total
    total = int(round(
        support_score   * 0.30 +
        adhesion_score  * 0.25 +
        stability_score * 0.20 +
        detail_score    * 0.15 +
        bridge_score    * 0.10
    ))
    total = max(0, min(100, total))

    # Difficulty label
    if total >= 80:
        difficulty_label = "Easy"
    elif total >= 60:
        difficulty_label = "Moderate"
    elif total >= 40:
        difficulty_label = "Challenging"
    else:
        difficulty_label = "Difficult"

    # Actionable warnings — shown to the user alongside the score
    warnings: list[str] = []

    if support_score < 40:
        warnings.append("Heavy overhangs — supports will be generated")
    elif support_score < 65:
        warnings.append("Some overhangs detected — support settings adjusted")

    if adhesion_score < 40:
        warnings.append("Very small bed contact area — brim strongly recommended")
    elif adhesion_score < 65:
        warnings.append("Limited bed contact area — brim enabled")

    if stability_score < 40:
        warnings.append("Tall narrow model — tip-over risk during printing")
    elif stability_score < 65:
        warnings.append("Elevated height-to-base ratio — speed reduced for stability")

    if detail_score < 40:
        warnings.append("Very fine features detected — use 0.4 mm or smaller nozzle")
    elif detail_score < 65:
        warnings.append("Fine features present — layer height reduced")

    if bridge_score < 50:
        warnings.append("Long bridge spans — maximum cooling required")

    return PrintabilityScore(
        total=total,
        support_score=support_score,
        adhesion_score=adhesion_score,
        stability_score=stability_score,
        detail_score=detail_score,
        bridge_score=bridge_score,
        difficulty_label=difficulty_label,
        warnings=warnings,
    )
