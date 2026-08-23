"""Translation orchestration with a separate deterministic optimization plan."""

from dataclasses import dataclass

from app.models.print_settings import PrintSettings as LegacyPrintSettings
from app.models.printer import FilamentType, PrinterProfile
from app.threemf.domain.diagnostics import (
    Severity,
    TranslationItem,
    TranslationReport,
    TranslationStatus,
)
from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.metadata import SlicerType
from app.threemf.domain.settings import ConversionContext, ConversionMode, PrintSettings
from app.threemf.intelligence.analyzer import ProjectAnalyzer
from app.threemf.intelligence.engine import AutoSliceDecisionEngine
from app.threemf.intelligence.models import AutoSliceProfile, OptimizationMode, OptimizationPlan
from app.threemf.intelligence.profiles import build_target_profile
from app.threemf.translation.plan import TranslationPlan, build_translation_plan


@dataclass(frozen=True)
class TargetArtifacts:
    settings: LegacyPrintSettings
    printer: PrinterProfile
    filament: FilamentType


@dataclass(frozen=True)
class TranslationOutcome:
    document: Universal3MFDocument
    report: TranslationReport
    target_artifacts: TargetArtifacts
    plan: TranslationPlan | None = None
    optimization_plan: OptimizationPlan | None = None


class AutoSliceTranslationEngine:
    def translate(
        self, document: Universal3MFDocument, context: ConversionContext
    ) -> TranslationOutcome:
        target = SlicerType(context.target_slicer)
        translation_plan = build_translation_plan(document, target)
        if (
            context.mode is not ConversionMode.AUTOSLICE
            or context.preserve_source
            or not context.optimize_for_target
        ):
            return TranslationOutcome(
                document,
                translation_plan.report,
                TargetArtifacts(None, None, None),
                translation_plan,
            )
        if not context.target_printer_id:
            raise ValueError("AutoSlice conversion requires a target printer profile.")
        profile = build_target_profile(
            context.target_slicer,
            context.target_printer_id,
            context.nozzle_size_mm or 0.4,
            context.material_id or "pla",
        )
        analysis = ProjectAnalyzer().analyze(document, profile)
        optimizer = AutoSliceDecisionEngine()
        autoslice_profile = AutoSliceProfile(
            mode={
                "balanced": OptimizationMode.BALANCED,
                "quality": OptimizationMode.QUALITY_FIRST,
                "fast": OptimizationMode.FAST_PRINT,
                "material_saving": OptimizationMode.MATERIAL_SAVING,
            }.get(context.optimization_profile, OptimizationMode.BALANCED)
        )
        optimization_plan = optimizer.evaluate(
            document, analysis, profile, context.mode, autoslice_profile
        )
        optimized = optimizer.apply(document, optimization_plan, profile, autoslice_profile)
        optimization_items = tuple(
            TranslationItem(
                item.setting,
                TranslationStatus.APPROXIMATED,
                Severity.MEDIUM,
                source_value=str(item.old_value),
                universal_value=str(item.new_value),
                target_value=str(item.new_value),
                reason=f"{item.reason} Rule={item.rule}; confidence={item.confidence.value}.",
            )
            for item in optimization_plan.changes
        )
        combined = TranslationReport(
            translation_plan.operations + optimization_items
        ).with_weighted_score()
        return TranslationOutcome(
            optimized,
            combined,
            TargetArtifacts(None, None, None),
            translation_plan,
            optimization_plan,
        )


def _universal_settings(settings: LegacyPrintSettings) -> PrintSettings:
    return PrintSettings(
        layer_height_mm=settings.layer_height_mm,
        first_layer_height_mm=settings.first_layer_height_mm,
        wall_count=settings.wall_count,
        top_layers=settings.top_layers,
        bottom_layers=settings.bottom_layers,
        infill_density_percent=settings.infill_percent,
        infill_pattern=settings.infill_pattern,
        print_speed_mm_s=settings.print_speed_mm_s,
        first_layer_speed_mm_s=settings.first_layer_speed_mm_s,
        nozzle_temperature_c=settings.nozzle_temp_c,
        bed_temperature_c=settings.bed_temp_c,
        fan_speed_percent=settings.fan_speed_percent,
        extrusion_width_mm=settings.line_width_mm,
        ironing_enabled=settings.ironing_enabled,
        seam_position=settings.seam_position,
    )


def _settings_report(
    source: PrintSettings, target: PrintSettings, context: ConversionContext
) -> TranslationReport:
    items: list[TranslationItem] = []
    for feature in (
        "layer_height_mm",
        "wall_count",
        "infill_density_percent",
        "infill_pattern",
        "nozzle_temperature_c",
        "bed_temperature_c",
        "print_speed_mm_s",
    ):
        before = getattr(source, feature)
        after = getattr(target, feature)
        status = (
            TranslationStatus.SUPPORTED
            if before == after or before is None
            else TranslationStatus.APPROXIMATED
        )
        items.append(
            TranslationItem(
                feature,
                status,
                Severity.MEDIUM if status is TranslationStatus.APPROXIMATED else Severity.INFO,
                source_value=None if before is None else str(before),
                universal_value=None if before is None else str(before),
                target_value=None if after is None else str(after),
                reason=(
                    f"AutoSlice optimized this setting for printer {context.target_printer_id}."
                    if status is TranslationStatus.APPROXIMATED
                    else "Setting is supported by the target profile."
                ),
            )
        )
    return TranslationReport(tuple(items))
