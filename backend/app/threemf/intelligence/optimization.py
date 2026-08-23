"""Deterministic multi-objective print-setting candidate evaluation."""

from dataclasses import dataclass, field
from enum import Enum
from time import perf_counter

from app.threemf.domain.document import Universal3MFDocument
from app.threemf.intelligence.models import TargetProfile


class OptimizationProfile(str, Enum):
    BALANCED = "balanced"
    QUALITY = "quality"
    FAST = "fast"
    MATERIAL_SAVING = "material_saving"


class OptimizationObjective(str, Enum):
    QUALITY = "quality"
    SPEED = "speed"
    MATERIAL = "material"
    RELIABILITY = "reliability"


DEFAULT_WEIGHTS = {
    OptimizationProfile.BALANCED: (
        ("quality", 0.3),
        ("reliability", 0.35),
        ("speed", 0.2),
        ("material", 0.15),
    ),
    OptimizationProfile.QUALITY: (
        ("quality", 0.5),
        ("reliability", 0.3),
        ("speed", 0.1),
        ("material", 0.1),
    ),
    OptimizationProfile.FAST: (
        ("quality", 0.15),
        ("reliability", 0.25),
        ("speed", 0.5),
        ("material", 0.1),
    ),
    OptimizationProfile.MATERIAL_SAVING: (
        ("quality", 0.2),
        ("reliability", 0.3),
        ("speed", 0.1),
        ("material", 0.4),
    ),
}


@dataclass(frozen=True)
class ObjectiveWeights:
    values: tuple[tuple[str, float], ...]

    def __post_init__(self):
        if {name for name, _ in self.values} != {item.value for item in OptimizationObjective}:
            raise ValueError("Weights must define every optimization objective.")
        if abs(sum(value for _, value in self.values) - 1.0) > 1e-9 or any(
            value < 0 for _, value in self.values
        ):
            raise ValueError("Objective weights must be non-negative and total 1.0.")


@dataclass(frozen=True)
class OptimizationExplanation:
    setting: str
    old_value: object
    new_value: object
    why: str
    rule: str
    impact: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class OptimizationCandidate:
    candidate_id: str
    settings: tuple[tuple[str, object], ...]
    support_strategy: str | None
    objective_scores: tuple[tuple[str, float], ...]
    weighted_score: float
    viable: bool
    hard_limit_violations: tuple[str, ...]


@dataclass(frozen=True)
class AdvancedOptimizationResult:
    profile: OptimizationProfile
    weights: ObjectiveWeights
    selected: OptimizationCandidate
    candidates: tuple[OptimizationCandidate, ...]
    explanations: tuple[OptimizationExplanation, ...]
    analyze_only: bool
    benchmark_ms: float = field(compare=False)


class AdvancedPrintOptimizationEngine:
    def optimize(
        self,
        document: Universal3MFDocument,
        target: TargetProfile,
        profile: OptimizationProfile = OptimizationProfile.BALANCED,
        weights: ObjectiveWeights | None = None,
        *,
        analyze_only: bool = True,
        hard_blocked: bool = False,
    ) -> AdvancedOptimizationResult:
        started = perf_counter()
        weights = weights or ObjectiveWeights(DEFAULT_WEIGHTS[profile])
        source = self._source(document, target)
        variants = (
            ("preserve", source),
            (
                "balanced",
                {
                    **source,
                    "layer_height_mm": target.nozzle.recommended_layer_height_mm,
                    "print_speed_mm_s": _clamp(
                        source["print_speed_mm_s"], *target.filament.recommended_speed_mm_s
                    ),
                },
            ),
            (
                "quality",
                {
                    **source,
                    "layer_height_mm": max(
                        target.nozzle.minimum_layer_height_mm,
                        min(
                            target.nozzle.recommended_layer_height_mm * 0.8,
                            target.nozzle.maximum_layer_height_mm,
                        ),
                    ),
                    "wall_count": max(source["wall_count"], 3),
                    "print_speed_mm_s": max(
                        target.filament.recommended_speed_mm_s[0], source["print_speed_mm_s"] * 0.7
                    ),
                },
            ),
            (
                "fast",
                {
                    **source,
                    "layer_height_mm": min(
                        target.nozzle.maximum_layer_height_mm,
                        max(
                            target.nozzle.recommended_layer_height_mm,
                            target.nozzle.diameter_mm * 0.65,
                        ),
                    ),
                    "print_speed_mm_s": min(
                        target.printer.speed_limit_mm_s, target.filament.recommended_speed_mm_s[1]
                    ),
                },
            ),
            (
                "material_saving",
                {
                    **source,
                    "layer_height_mm": min(
                        target.nozzle.maximum_layer_height_mm,
                        max(
                            target.nozzle.recommended_layer_height_mm,
                            target.nozzle.diameter_mm * 0.6,
                        ),
                    ),
                    "wall_count": min(source["wall_count"], 2),
                    "infill_density_percent": min(source["infill_density_percent"], 10.0),
                },
            ),
        )
        candidates = tuple(
            self._candidate(
                name, settings, document.supports.support_type, target, weights, hard_blocked
            )
            for name, settings in variants
        )
        preferred = {
            OptimizationProfile.BALANCED: "balanced",
            OptimizationProfile.QUALITY: "quality",
            OptimizationProfile.FAST: "fast",
            OptimizationProfile.MATERIAL_SAVING: "material_saving",
        }[profile]
        ranked = sorted(
            candidates,
            key=lambda item: (
                not item.viable,
                -item.weighted_score,
                item.candidate_id != preferred,
                item.candidate_id,
            ),
        )
        selected = ranked[0]
        baseline = next(item for item in candidates if item.candidate_id == "preserve")
        old = dict(source)
        new = dict(selected.settings)
        before = dict(baseline.objective_scores)
        after = dict(selected.objective_scores)
        explanations = tuple(
            OptimizationExplanation(
                key,
                old[key],
                new[key],
                "Selected by measurable target-aware objective scoring.",
                f"OPTIMIZATION_{profile.value.upper()}",
                tuple(
                    (objective, round(after[objective] - before[objective], 2))
                    for objective in sorted(after)
                ),
            )
            for key in sorted(new)
            if new[key] != old[key]
        )
        return AdvancedOptimizationResult(
            profile,
            weights,
            selected,
            tuple(sorted(candidates, key=lambda item: item.candidate_id)),
            explanations,
            analyze_only,
            round((perf_counter() - started) * 1000, 4),
        )

    def _source(self, document, target):
        process = document.process
        return {
            "layer_height_mm": process.layer_height_mm or target.nozzle.recommended_layer_height_mm,
            "wall_count": process.wall_count or 3,
            "infill_density_percent": process.infill_density_percent
            if process.infill_density_percent is not None
            else 15.0,
            "print_speed_mm_s": process.print_speed_mm_s
            or min(100.0, target.printer.speed_limit_mm_s),
            "nozzle_temperature_c": process.nozzle_temperature_c
            or sum(target.filament.temperature_range_c) // 2,
            "bed_temperature_c": process.bed_temperature_c
            or sum(target.filament.bed_temperature_range_c) // 2,
            "fan_speed_percent": process.fan_speed_percent
            if process.fan_speed_percent is not None
            else target.filament.cooling_range_percent[1],
        }

    def _candidate(self, name, settings, support, target, weights, hard_blocked):
        violations = []
        layer = settings["layer_height_mm"]
        temp = settings["nozzle_temperature_c"]
        bed = settings["bed_temperature_c"]
        speed = settings["print_speed_mm_s"]
        if hard_blocked:
            violations.append("PROJECT_HARD_LIMIT")
        if (
            not target.nozzle.minimum_layer_height_mm
            <= layer
            <= target.nozzle.maximum_layer_height_mm
        ):
            violations.append("NOZZLE_LAYER_HEIGHT_LIMIT")
        if (
            not target.filament.temperature_range_c[0]
            <= temp
            <= target.filament.temperature_range_c[1]
        ):
            violations.append("MATERIAL_TEMPERATURE_LIMIT")
        if (
            not target.filament.bed_temperature_range_c[0]
            <= bed
            <= target.filament.bed_temperature_range_c[1]
        ):
            violations.append("BED_TEMPERATURE_LIMIT")
        if speed > target.printer.speed_limit_mm_s:
            violations.append("PRINTER_SPEED_LIMIT")
        walls = settings["wall_count"]
        infill = settings["infill_density_percent"]
        maxlayer = target.nozzle.maximum_layer_height_mm
        maxspeed = max(target.filament.recommended_speed_mm_s[1], 1)
        scores = {
            "quality": max(0.0, min(100.0, 100 - 45 * layer / maxlayer + 7 * min(walls, 5))),
            "speed": max(0.0, min(100.0, 65 * speed / maxspeed + 35 * layer / maxlayer)),
            "material": max(
                0.0,
                min(
                    100.0,
                    100 - 1.8 * infill - 7 * walls - (8 if support and support != "none" else 0),
                ),
            ),
            "reliability": max(
                0.0,
                min(
                    100.0,
                    100
                    - max(0.0, speed - target.filament.recommended_speed_mm_s[1]) * 0.3
                    - (15 if walls < 2 else 0),
                ),
            ),
        }
        weighted = sum(scores[key] * value for key, value in weights.values)
        viable = not violations
        return OptimizationCandidate(
            name,
            tuple(sorted(settings.items())),
            support,
            tuple((key, round(scores[key], 2)) for key in sorted(scores)),
            round(weighted if viable else -1.0, 2),
            viable,
            tuple(violations),
        )


def _clamp(value, minimum, maximum):
    return min(max(value, minimum), maximum)
