"""Deterministic prioritized rules and conflict resolution."""

from dataclasses import replace

from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.settings import ConversionMode
from app.threemf.intelligence.models import (
    AutoSliceProfile,
    CompatibilityBreakdown,
    Confidence,
    GeometryTransformChange,
    OptimizationChange,
    OptimizationPlan,
    PlanMessage,
    PlanStatus,
    ProjectAnalysis,
    RulePriority,
    SupportChange,
    TargetProfile,
)

AUTOMATIC_SETTING_ALLOWLIST = frozenset(
    {
        "layer_height_mm",
        "first_layer_height_mm",
        "nozzle_temperature_c",
        "bed_temperature_c",
        "fan_speed_percent",
        "print_speed_mm_s",
        "infill_density_percent",
        "wall_count",
    }
)


class AutoSliceDecisionEngine:
    def evaluate(
        self,
        document: Universal3MFDocument,
        analysis: ProjectAnalysis,
        target: TargetProfile,
        mode: ConversionMode = ConversionMode.AUTOSLICE,
        profile: AutoSliceProfile | None = None,
    ) -> OptimizationPlan:
        profile = profile or AutoSliceProfile()
        warnings: list[PlanMessage] = []
        blocked: list[PlanMessage] = []
        recommendations: list[PlanMessage] = []
        candidates: list[OptimizationChange] = []

        if analysis.build_volume_status is PlanStatus.OUTSIDE_BUILD_VOLUME:
            blocked.append(
                PlanMessage(
                    "BUILD_VOLUME_LIMIT",
                    "Model exceeds target build volume.",
                    "BUILD_VOLUME_LIMIT",
                    RulePriority.HARD_LIMIT,
                )
            )
        elif analysis.build_volume_status is PlanStatus.NEAR_LIMIT:
            warnings.append(
                PlanMessage(
                    "BUILD_VOLUME_NEAR_LIMIT",
                    "Model is within 10% of a target build-volume limit.",
                    "BUILD_VOLUME_LIMIT",
                    RulePriority.HARD_LIMIT,
                )
            )

        material_types = {value.lower() for value in analysis.material_ids}
        source_types = {
            str(item.filament_type or item.material_type or "").lower()
            for item in document.materials
        }
        declared_types = {value for value in source_types if value}
        if target.filament.material_id not in target.printer.supported_materials:
            blocked.append(
                PlanMessage(
                    "FILAMENT_COMPATIBILITY",
                    f"{target.filament.material_id.upper()} is not supported by {target.printer.display_name}.",
                    "FILAMENT_COMPATIBILITY",
                    RulePriority.COMPATIBILITY,
                )
            )
        if declared_types and target.filament.material_id not in declared_types:
            warnings.append(
                PlanMessage(
                    "SOURCE_TARGET_MATERIAL_MISMATCH",
                    "Source material differs from the selected target filament; no material was substituted.",
                    "FILAMENT_COMPATIBILITY",
                    RulePriority.COMPATIBILITY,
                    Confidence.MEDIUM,
                )
            )
        if (
            max(len(material_types), len(document.tool_assignments), len(declared_types))
            > target.printer.max_tools
        ):
            blocked.append(
                PlanMessage(
                    "TOOL_CAPABILITY",
                    "Project requires more material tools than the target printer provides.",
                    "TOOL_CAPABILITY",
                    RulePriority.COMPATIBILITY,
                )
            )

        layer = document.process.layer_height_mm
        nozzle = target.nozzle
        if (
            layer is not None
            and not nozzle.minimum_layer_height_mm <= layer <= nozzle.maximum_layer_height_mm
        ):
            candidates.append(
                OptimizationChange(
                    "layer_height_mm",
                    layer,
                    nozzle.recommended_layer_height_mm,
                    f"Target {nozzle.diameter_mm:g} mm nozzle supports {nozzle.minimum_layer_height_mm:g}-{nozzle.maximum_layer_height_mm:g} mm layers.",
                    "NOZZLE_LAYER_HEIGHT_RANGE",
                    Confidence.HIGH,
                    RulePriority.QUALITY,
                    "quality",
                )
            )
        first = document.process.first_layer_height_mm
        if (
            first is not None
            and not nozzle.minimum_layer_height_mm <= first <= nozzle.maximum_layer_height_mm
        ):
            candidates.append(
                OptimizationChange(
                    "first_layer_height_mm",
                    first,
                    nozzle.recommended_layer_height_mm,
                    "First-layer height is outside the target nozzle's supported range.",
                    "NOZZLE_FIRST_LAYER_HEIGHT_RANGE",
                    Confidence.HIGH,
                    RulePriority.QUALITY,
                    "reliability",
                )
            )

        for setting, value, limits, rule in (
            (
                "nozzle_temperature_c",
                document.process.nozzle_temperature_c,
                target.filament.temperature_range_c,
                "MATERIAL_TEMPERATURE_RANGE",
            ),
            (
                "bed_temperature_c",
                document.process.bed_temperature_c,
                target.filament.bed_temperature_range_c,
                "MATERIAL_BED_TEMPERATURE_RANGE",
            ),
        ):
            if value is not None and not limits[0] <= value <= limits[1]:
                new = min(max(value, limits[0]), limits[1])
                candidates.append(
                    OptimizationChange(
                        setting,
                        value,
                        new,
                        f"Selected {target.filament.material_id.upper()} profile permits {limits[0]}-{limits[1]} C.",
                        rule,
                        Confidence.HIGH,
                        RulePriority.COMPATIBILITY,
                        "material",
                    )
                )

        # Highest priority wins; ties are resolved by stable rule id, never evaluation order.
        winners: dict[str, OptimizationChange] = {}
        for change in sorted(
            candidates, key=lambda item: (item.setting, -int(item.priority), item.rule)
        ):
            winners.setdefault(change.setting, change)
        changes = (
            tuple(winners[key] for key in sorted(winners))
            if mode is ConversionMode.AUTOSLICE
            else ()
        )
        if mode is not ConversionMode.AUTOSLICE:
            recommendations.extend(
                PlanMessage(
                    change.rule, change.reason, change.rule, change.priority, change.confidence
                )
                for change in winners.values()
            )
        known = {name for name, _ in analysis.settings}
        unchanged = tuple(sorted(known - set(winners if mode is ConversionMode.AUTOSLICE else ())))
        issue_weight = len(warnings) * 2 + len(blocked) * 20
        optimization_impact = max(0.0, 100.0 - len(changes) * 2.0)
        target_score = max(0.0, 100.0 - issue_weight)
        final = (
            min(target_score, optimization_impact)
            if blocked
            else round((target_score * 0.7 + optimization_impact * 0.3), 2)
        )
        total = max(1, len(known) + len(warnings) + len(blocked))
        breakdown = CompatibilityBreakdown(
            100.0,
            target_score,
            optimization_impact,
            final,
            round(100 * len(unchanged) / total, 2),
            round(100 * len(changes) / total, 2),
            round(100 * len(recommendations) / total, 2),
            round(100 * len(blocked) / total, 2),
        )
        from app.threemf.intelligence.geometry import GeometryAnalyzer

        geometry = GeometryAnalyzer().analyze(document, target, profile)
        geometry_changes = []
        if len(geometry.objects) == 1 and geometry.objects[0].orientation:
            rec = geometry.objects[0].orientation
            if rec.rotation_degrees != (0.0, 0.0, 0.0):
                applied = (
                    mode is ConversionMode.AUTOSLICE
                    and not blocked
                    and profile.orientation_mode.value == "auto"
                    and rec.apply_automatically
                    and {Confidence.LOW: 1, Confidence.MEDIUM: 2, Confidence.HIGH: 3}[
                        rec.confidence
                    ]
                    >= {Confidence.LOW: 1, Confidence.MEDIUM: 2, Confidence.HIGH: 3}[
                        profile.orientation_confidence_threshold
                    ]
                    and rec.score - rec.current_score >= profile.orientation_improvement_threshold
                )
                geometry_changes.append(
                    GeometryTransformChange(
                        geometry.objects[0].object_id,
                        rec.current_transform,
                        rec.recommended_transform,
                        rec.rotation_degrees,
                        rec.reason,
                        "ORIENTATION_SCORE",
                        rec.confidence,
                        round(rec.score - rec.current_score, 2),
                        applied,
                    )
                )
        for item in geometry.diagnostics:
            warnings.append(PlanMessage(item.code, item.message, item.code, RulePriority.QUALITY))
        from app.threemf.intelligence.support import SupportAnalyzer, SupportStrategy

        support_plan = SupportAnalyzer().analyze(document, geometry, target, mode)
        support_changes = []
        if support_plan.strategy is not SupportStrategy.NONE:
            support_changes.extend(
                (
                    SupportChange(
                        "supports.enabled",
                        document.supports.enabled,
                        True,
                        f"{len(support_plan.required_regions)} required and {len(support_plan.optional_regions)} optional support regions.",
                        "SUPPORT_REGION_PLAN",
                        support_plan.confidence,
                        support_plan.applied,
                    ),
                    SupportChange(
                        "supports.support_type",
                        document.supports.support_type,
                        support_plan.strategy.value,
                        "Target-supported strategy selected from analyzed regions.",
                        "SUPPORT_STRATEGY",
                        support_plan.confidence,
                        support_plan.applied,
                    ),
                )
            )
        return OptimizationPlan(
            changes=changes,
            unchanged=unchanged,
            warnings=tuple(warnings),
            blocked=tuple(blocked),
            recommendations=tuple(recommendations),
            geometry_changes=tuple(geometry_changes),
            support_changes=tuple(support_changes),
            compatibility=breakdown,
        )

    def apply(
        self,
        document: Universal3MFDocument,
        plan: OptimizationPlan,
        target: TargetProfile | None = None,
        profile: AutoSliceProfile | None = None,
    ) -> Universal3MFDocument:
        if not plan.can_convert:
            raise ValueError(
                "Optimization plan is blocked: " + "; ".join(item.message for item in plan.blocked)
            )
        updates = {
            item.setting: item.new_value
            for item in plan.changes
            if item.setting in AUTOMATIC_SETTING_ALLOWLIST
        }
        optimized = (
            replace(document, process=replace(document.process, **updates)) if updates else document
        )
        applied = {item.object_id: item for item in plan.geometry_changes if item.applied}
        if applied:
            from app.threemf.domain.geometry import Transform

            items = tuple(
                replace(item, transform=Transform(applied[item.object_id].recommended_transform))
                if item.object_id in applied
                else item
                for item in optimized.build.items
            )
            optimized = replace(optimized, build=replace(optimized.build, items=items))
            if target:
                from app.threemf.intelligence.geometry import GeometryAnalyzer, PrintabilityStatus

                checked = GeometryAnalyzer().analyze(
                    optimized, target, profile or AutoSliceProfile()
                )
                if checked.status is PrintabilityStatus.BLOCKED or checked.collisions:
                    raise ValueError("Geometry transform rejected by mandatory re-analysis.")
        support_updates = {
            item.setting.split(".", 1)[1]: item.new_value
            for item in plan.support_changes
            if item.applied
        }
        if support_updates:
            optimized = replace(optimized, supports=replace(optimized.supports, **support_updates))
        return optimized
