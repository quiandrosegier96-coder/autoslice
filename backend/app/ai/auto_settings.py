"""
AutoSlice — AI auto-settings engine.

run(request) → AutoSettingsResponse
features_from_geometry(geometry, nozzle_mm) → ModelFeatures  ← pipeline bridge

Pure functions. No side effects. No I/O. No external AI APIs.
Logic-based heuristics calibrated against FDM printing best practices.

Pipeline:
  1. _compute_risk  — derive per-dimension risk scores from geometry features
  2. _gen_settings  — translate features + risk + intent into slicer parameters
  3. _gen_warnings  — emit actionable warnings from features, settings, and risk
"""

from __future__ import annotations

from app.ai.schemas import (
    AIAdhesionSettings,
    AIGeneratedSettings,
    AIInfillSettings,
    AILayerSettings,
    AISpeedSettings,
    AISupportSettings,
    AutoSettingsRequest,
    AutoSettingsResponse,
    ConvertHints,
    DimensionRisk,
    FilamentType,
    ModelFeatures,
    PrintRiskScore,
    PrintWarning,
    RiskLevel,
    WarningSeverity,
)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _risk_level(value: int) -> RiskLevel:
    if value >= 60:
        return RiskLevel.HIGH
    if value >= 35:
        return RiskLevel.MEDIUM
    if value >= 15:
        return RiskLevel.LOW
    return RiskLevel.NONE


def _dim_risk(label: str, value: int) -> DimensionRisk:
    clamped = min(100, value)
    return DimensionRisk(label=label, value=clamped, level=_risk_level(clamped))


def _nozzle_step(value: float, step: float = 0.05) -> float:
    """Round to the nearest slicer-friendly increment (default 0.05 mm)."""
    return round(round(value / step) * step, 3)


# ─────────────────────────────────────────────────────────────────────────────
# Risk scoring — one function per dimension
# Each accumulates a 0–100 value through additive thresholds.
# ─────────────────────────────────────────────────────────────────────────────

def _overhang_risk(overhang_ratio: float) -> DimensionRisk:
    v = 0
    if overhang_ratio > 0.05:
        v += 15
    if overhang_ratio > 0.15:
        v += 20
    if overhang_ratio > 0.30:
        v += 20
    if overhang_ratio > 0.50:
        v += 20
    if overhang_ratio > 0.70:
        v += 15
    return _dim_risk("overhang", v)


def _thin_wall_risk(thin_wall_ratio: float) -> DimensionRisk:
    v = 0
    if thin_wall_ratio > 0.02:
        v += 15
    if thin_wall_ratio > 0.10:
        v += 25
    if thin_wall_ratio > 0.25:
        v += 25
    if thin_wall_ratio > 0.45:
        v += 20
    return _dim_risk("thin_wall", v)


def _stability_risk(height_mm: float, volume_cm3: float) -> DimensionRisk:
    """
    Aspect proxy: height_mm divided by cube-root of volume (converted to mm).
    Approximates the height-to-base ratio without needing contact area geometry.
    aspect ~ 1.0 → roughly spherical (stable)
    aspect > 3.5 → tall and narrow (unstable)
    """
    cube_root_mm = (volume_cm3 ** (1.0 / 3.0)) * 10.0
    aspect = height_mm / max(cube_root_mm, 1.0)
    v = 0
    if aspect > 2.0:
        v += 15
    if aspect > 3.5:
        v += 20
    if aspect > 5.0:
        v += 20
    if aspect > 7.0:
        v += 20
    return _dim_risk("stability", v)


def _volume_risk(volume_cm3: float, filament: FilamentType) -> DimensionRisk:
    warping_filaments = {FilamentType.ABS, FilamentType.ASA, FilamentType.NYLON}
    v = 0
    if volume_cm3 < 0.5:
        v += 30   # very small: adhesion and detail issues
    elif volume_cm3 < 2.0:
        v += 10
    if volume_cm3 > 200 and filament in warping_filaments:
        v += 25   # large model + warp-prone material
    if volume_cm3 > 400:
        v += 20   # any large model adds risk
    return _dim_risk("volume", v)


def _compute_risk(features: ModelFeatures, filament: FilamentType) -> PrintRiskScore:
    overhang  = _overhang_risk(features.overhang_ratio)
    thin_wall = _thin_wall_risk(features.thin_wall_ratio)
    stability = _stability_risk(features.height_mm, features.volume_cm3)
    volume    = _volume_risk(features.volume_cm3, filament)

    overall = min(100, max(
        overhang.value,
        thin_wall.value,
        stability.value,
        volume.value,
    ))

    return PrintRiskScore(
        overall   = overall,
        level     = _risk_level(overall),
        overhang  = overhang,
        thin_wall = thin_wall,
        stability = stability,
        volume    = volume,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Settings generation — look-up tables + risk-driven overrides
# ─────────────────────────────────────────────────────────────────────────────

_FILAMENT_TEMPS: dict[FilamentType, tuple[int, int]] = {
    FilamentType.PLA:   (210, 60),
    FilamentType.PETG:  (235, 70),
    FilamentType.ABS:   (245, 100),
    FilamentType.ASA:   (250, 100),
    FilamentType.TPU:   (225, 60),
    FilamentType.NYLON: (260, 80),
}

_LAYER_RATIOS: dict[str, float] = {
    "draft":    0.60,
    "standard": 0.40,
    "quality":  0.25,
}

_INFILL_PERCENT: dict[str, int] = {
    "draft":    15,
    "standard": 20,
    "quality":  35,
}

_INFILL_PATTERN: dict[str, str] = {
    "draft":    "grid",
    "standard": "gyroid",
    "quality":  "gyroid",
}

_WALL_COUNTS: dict[str, int] = {
    "draft":    2,
    "standard": 3,
    "quality":  4,
}

_BASE_SPEEDS: dict[str, int] = {
    "draft":    80,
    "standard": 60,
    "quality":  40,
}


def _top_bottom_layers(layer_height_mm: float) -> int:
    """Target a solid shell of ~0.8 mm regardless of layer height."""
    return max(3, round(0.8 / max(layer_height_mm, 0.05)))


def _fan_speed(filament: FilamentType, quality_intent: str) -> int:
    no_cooling = {FilamentType.ABS, FilamentType.ASA, FilamentType.NYLON}
    if filament in no_cooling:
        return 0
    if filament == FilamentType.TPU:
        return 50
    return 80 if quality_intent == "draft" else 100


def _gen_settings(
    features: ModelFeatures,
    risk: PrintRiskScore,
    filament: FilamentType,
    nozzle_mm: float,
    quality_intent: str,
) -> AIGeneratedSettings:
    # --- Layer height ---
    lh       = _nozzle_step(nozzle_mm * _LAYER_RATIOS[quality_intent])
    lh       = max(0.05, min(lh, nozzle_mm * 0.75))  # never exceed 75 % of nozzle
    first_lh = _nozzle_step(min(nozzle_mm * 0.5, 0.30))

    # --- Supports ---
    need_supports   = features.overhang_ratio > 0.08
    support_type_   = "tree" if features.overhang_ratio > 0.25 else "normal"
    support_density = 20 if risk.overhang.level in (RiskLevel.MEDIUM, RiskLevel.HIGH) else 15
    angle_thresh    = 55 if risk.overhang.level == RiskLevel.HIGH else 45

    # --- Adhesion ---
    warping_filaments = {FilamentType.ABS, FilamentType.ASA, FilamentType.NYLON}
    needs_brim = (
        risk.stability.level in (RiskLevel.MEDIUM, RiskLevel.HIGH)
        or filament in warping_filaments
        or features.overhang_ratio > 0.40
    )
    brim_width = 8.0 if filament in warping_filaments else 5.0

    # --- Infill ---
    infill_pct = _INFILL_PERCENT[quality_intent]
    if features.thin_wall_ratio > 0.20:
        infill_pct = max(infill_pct, 25)  # more infill to back thin features

    # --- Speed ---
    speed = _BASE_SPEEDS[quality_intent]
    if filament == FilamentType.TPU:
        speed = min(speed, 30)
    if risk.overhang.level == RiskLevel.HIGH:
        speed = max(20, speed - 15)  # slow down for difficult overhangs
    first_layer_speed = max(10, min(20, speed // 3))

    # --- Walls ---
    walls = _WALL_COUNTS[quality_intent]
    if features.thin_wall_ratio > 0.15:
        walls = max(walls, 3)

    nozzle_t, bed_t = _FILAMENT_TEMPS[filament]
    layers           = _top_bottom_layers(lh)

    return AIGeneratedSettings(
        layer=AILayerSettings(
            height_mm             = lh,
            first_layer_height_mm = first_lh,
        ),
        support=AISupportSettings(
            enabled             = need_supports,
            type                = support_type_ if need_supports else "none",
            density_percent     = support_density,
            angle_threshold_deg = angle_thresh,
        ),
        adhesion=AIAdhesionSettings(
            brim_enabled  = needs_brim,
            brim_width_mm = brim_width if needs_brim else 0.0,
        ),
        infill=AIInfillSettings(
            percent = infill_pct,
            pattern = _INFILL_PATTERN[quality_intent],
        ),
        speed=AISpeedSettings(
            print_mm_s       = speed,
            first_layer_mm_s = first_layer_speed,
            fan_percent      = _fan_speed(filament, quality_intent),
        ),
        wall_count    = walls,
        top_layers    = layers,
        bottom_layers = layers,
        nozzle_temp_c = nozzle_t,
        bed_temp_c    = bed_t,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Warnings — actionable messages raised from feature thresholds
# ─────────────────────────────────────────────────────────────────────────────

def _gen_warnings(
    features: ModelFeatures,
    settings: AIGeneratedSettings,
    risk: PrintRiskScore,
    filament: FilamentType,
) -> list[PrintWarning]:
    warnings: list[PrintWarning] = []

    def warn(
        code: str,
        severity: WarningSeverity,
        message: str,
        field: str | None = None,
    ) -> None:
        warnings.append(PrintWarning(code=code, severity=severity, message=message, field=field))

    # --- Overhang ---
    if features.overhang_ratio > 0.50:
        warn(
            "HIGH_OVERHANG",
            WarningSeverity.ERROR,
            f"Overhang ratio {features.overhang_ratio:.0%} is very high. "
            "Tree supports have been enabled — verify placement before slicing.",
            field="overhang_ratio",
        )
    elif features.overhang_ratio > 0.25:
        warn(
            "MODERATE_OVERHANG",
            WarningSeverity.WARNING,
            f"Overhang ratio {features.overhang_ratio:.0%} exceeds 25 %. "
            "Supports enabled. Consider reorienting the model to reduce support material.",
            field="overhang_ratio",
        )

    # --- Thin walls ---
    if features.thin_wall_ratio > 0.30:
        warn(
            "CRITICAL_THIN_WALLS",
            WarningSeverity.ERROR,
            f"Thin-wall ratio {features.thin_wall_ratio:.0%} is critically high. "
            "Many features may be lost at 0.4 mm nozzle width — consider a finer nozzle.",
            field="thin_wall_ratio",
        )
    elif features.thin_wall_ratio > 0.10:
        warn(
            "THIN_WALLS",
            WarningSeverity.WARNING,
            f"Thin-wall ratio {features.thin_wall_ratio:.0%} detected. "
            "Wall count has been increased. Surface quality may vary on narrow features.",
            field="thin_wall_ratio",
        )

    # --- Stability ---
    if risk.stability.level == RiskLevel.HIGH:
        warn(
            "STABILITY_RISK",
            WarningSeverity.ERROR,
            "Model aspect ratio indicates a tall, narrow geometry with high tip-over risk. "
            "Brim applied. Consider adding a custom base or splitting the model.",
            field="height_mm",
        )
    elif risk.stability.level == RiskLevel.MEDIUM:
        warn(
            "STABILITY_CONCERN",
            WarningSeverity.WARNING,
            "Model is tall relative to its volume. Brim enabled for added bed adhesion.",
            field="height_mm",
        )

    # --- Volume ---
    if features.volume_cm3 < 0.5:
        warn(
            "VERY_SMALL_MODEL",
            WarningSeverity.WARNING,
            f"Model volume {features.volume_cm3:.2f} cm³ is very small. "
            "Bed adhesion and fine detail reproduction may be limited.",
            field="volume_cm3",
        )
    if features.volume_cm3 > 400:
        warn(
            "LARGE_MODEL",
            WarningSeverity.WARNING,
            f"Model volume {features.volume_cm3:.0f} cm³ is large. "
            "Expect extended print times and elevated warping risk.",
            field="volume_cm3",
        )

    # --- Filament-specific ---
    if filament in (FilamentType.ABS, FilamentType.ASA):
        warn(
            "WARPING_FILAMENT",
            WarningSeverity.INFO,
            f"{filament.value.upper()} requires a fully enclosed printer and stable ambient "
            "temperature to prevent warping and layer separation. Fan disabled.",
        )
    if filament == FilamentType.NYLON:
        warn(
            "HYGROSCOPIC_FILAMENT",
            WarningSeverity.INFO,
            "Nylon is highly hygroscopic. Dry the spool for 4–6 h at 70 °C before printing "
            "to avoid moisture-induced stringing and weak layer bonds.",
        )
    if filament == FilamentType.TPU:
        warn(
            "FLEXIBLE_FILAMENT",
            WarningSeverity.INFO,
            f"TPU requires slow speeds and a direct-drive extruder. "
            f"Print speed capped at {settings.speed.print_mm_s} mm/s.",
        )

    return warnings


# ─────────────────────────────────────────────────────────────────────────────
# Convert hints — Apply AI Settings bridge
#
# Maps the AI's suggestions onto the exact ConvertRequest fields the frontend
# can pass to POST /api/convert.  Only fields that are actual inputs to the
# rules engine are included here; everything else is advisory-only.
# ─────────────────────────────────────────────────────────────────────────────

# Build plate recommendations per filament.
# PETG bonds aggressively to smooth PEI — textured is safer.
# ABS/ASA/Nylon warp less on textured surfaces with proper bed temp.
_BUILD_PLATE: dict[FilamentType, str] = {
    FilamentType.PLA:   "smooth",
    FilamentType.PETG:  "textured",
    FilamentType.ABS:   "textured",
    FilamentType.ASA:   "textured",
    FilamentType.TPU:   "smooth",
    FilamentType.NYLON: "textured",
}

# Nozzle material recommendations per filament.
# Nylon is often glass- or carbon-filled; hardened steel prevents wear.
# All other materials in this enum are safe with standard brass.
_NOZZLE_TYPE: dict[FilamentType, str] = {
    FilamentType.PLA:   "brass",
    FilamentType.PETG:  "brass",
    FilamentType.ABS:   "brass",
    FilamentType.ASA:   "brass",
    FilamentType.TPU:   "brass",
    FilamentType.NYLON: "hardened_steel",
}


def _compute_hints(filament: FilamentType, nozzle_mm: float) -> ConvertHints:
    return ConvertHints(
        filament_type  = filament.value,
        nozzle_size_mm = nozzle_mm,
        nozzle_type    = _NOZZLE_TYPE[filament],
        build_plate    = _BUILD_PLATE[filament],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def run(request: AutoSettingsRequest) -> AutoSettingsResponse:
    """Full AI auto-settings pipeline — risk → settings → warnings → hints."""
    risk     = _compute_risk(request.features, request.filament)
    settings = _gen_settings(
        request.features,
        risk,
        request.filament,
        request.nozzle_mm,
        request.quality_intent,
    )
    warnings = _gen_warnings(request.features, settings, risk, request.filament)
    hints    = _compute_hints(request.filament, request.nozzle_mm)

    return AutoSettingsResponse(
        settings      = settings,
        risk          = risk,
        warnings      = warnings,
        convert_hints = hints,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline bridge — GeometryAnalysis → ModelFeatures
#
# The existing slicing pipeline produces a GeometryAnalysis dataclass (internal).
# This function translates it into the ModelFeatures Pydantic model that the AI
# engine expects, so the job-based endpoint can reuse the geometry pipeline
# without duplicating any analysis work.
#
# thin_wall_ratio is approximated from min_thickness_mm because the geometry
# analyzer reports a scalar thickness, not an area fraction.
# ─────────────────────────────────────────────────────────────────────────────

def features_from_geometry(geometry: object, nozzle_mm: float = 0.4) -> ModelFeatures:
    """
    Translate a GeometryAnalysis dataclass into ModelFeatures.
    Accepts `object` to avoid a hard import of the internal dataclass.
    """
    return ModelFeatures(
        height_mm       = geometry.bounding_box.z_mm,
        volume_cm3      = geometry.estimated_volume_cm3,
        overhang_ratio  = geometry.overhang.overhang_area_ratio,
        thin_wall_ratio = _thin_wall_ratio_from_report(geometry.thin_wall, nozzle_mm),
    )


def _thin_wall_ratio_from_report(report: object, nozzle_mm: float) -> float:
    """
    Approximate a 0–1 thin-wall ratio from the ThinWallReport.

    The geometry analyzer stores the *thinnest* wall found, not a surface
    fraction, so we map thickness buckets (relative to nozzle diameter) to
    representative ratio values that drive the AI engine's risk and settings.
    """
    if not report.has_thin_walls:
        return 0.0
    t = report.min_thickness_mm
    if t >= 999.0:   # sentinel value — analyzer found no thin walls
        return 0.0
    if t < nozzle_mm:
        return 0.75  # below nozzle width — severe, many features will be lost
    if t < nozzle_mm * 2:
        return 0.40  # sub-double-nozzle — walls will under-extrude
    if t < nozzle_mm * 3:
        return 0.20  # borderline — surface quality will vary
    return 0.10      # marginal — risk is low but present
