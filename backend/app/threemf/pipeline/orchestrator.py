"""Single production pipeline snapshot from Universal3MF through translation planning."""

from dataclasses import dataclass, field
from time import perf_counter

from app.threemf.domain.diagnostics import (
    Severity,
    TranslationItem,
    TranslationReport,
    TranslationStatus,
)
from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.metadata import SlicerType
from app.threemf.domain.settings import ConversionContext
from app.threemf.intelligence.analyzer import ProjectAnalyzer
from app.threemf.intelligence.engine import AutoSliceDecisionEngine
from app.threemf.intelligence.geometry import GeometryAnalyzer, PrintabilityReport
from app.threemf.intelligence.models import (
    AutoSliceProfile,
    OptimizationMode,
    OptimizationPlan,
    ProjectAnalysis,
    TargetProfile,
)
from app.threemf.intelligence.placement import PlacementAnalyzer, PlacementPlan
from app.threemf.intelligence.profiles import build_target_profile
from app.threemf.intelligence.support import SupportAnalyzer, SupportPlan
from app.threemf.translation.plan import TranslationPlan, build_translation_plan


@dataclass(frozen=True)
class PipelineStage:
    name: str
    duration_ms: float = field(compare=False)
    status: str = "completed"


@dataclass(frozen=True)
class PipelineSnapshot:
    source_document: Universal3MFDocument
    optimized_document: Universal3MFDocument | None
    target: TargetProfile
    project: ProjectAnalysis
    printability: PrintabilityReport
    support_plan: SupportPlan
    placement_plan: PlacementPlan
    optimization_plan: OptimizationPlan
    translation_plan: TranslationPlan
    translation_report: TranslationReport
    stages: tuple[PipelineStage, ...]
    analyze_only: bool


class FullUniversal3MFPipeline:
    def analyze(
        self,
        document: Universal3MFDocument,
        context: ConversionContext,
        *,
        analyze_only: bool = True,
    ) -> PipelineSnapshot:
        if not context.target_printer_id:
            raise ValueError("Universal3MF pipeline requires a target printer profile.")
        stages = []

        def measure(name, operation):
            started = perf_counter()
            value = operation()
            stages.append(PipelineStage(name, (perf_counter() - started) * 1000))
            return value

        target = measure(
            "target_profile",
            lambda: build_target_profile(
                context.target_slicer,
                context.target_printer_id,
                context.nozzle_size_mm or 0.4,
                context.material_id or "pla",
                context.nozzle_material,
            ),
        )
        profile = AutoSliceProfile(
            mode={
                "balanced": OptimizationMode.BALANCED,
                "quality": OptimizationMode.QUALITY_FIRST,
                "fast": OptimizationMode.FAST_PRINT,
                "material_saving": OptimizationMode.MATERIAL_SAVING,
            }.get(context.optimization_profile, OptimizationMode.BALANCED)
        )
        project = measure("project_analysis", lambda: ProjectAnalyzer().analyze(document, target))
        printability = measure(
            "geometry_printability", lambda: GeometryAnalyzer().analyze(document, target, profile)
        )
        support = measure(
            "support_analysis",
            lambda: SupportAnalyzer().analyze(document, printability, target, context.mode),
        )
        placement = measure(
            "placement_analysis",
            lambda: PlacementAnalyzer().analyze(document, target, context.mode),
        )
        optimization = measure(
            "optimization",
            lambda: AutoSliceDecisionEngine().evaluate(
                document, project, target, context.mode, profile, analyze_only
            ),
        )
        optimized = (
            None
            if analyze_only
            else measure(
                "apply_reanalyze",
                lambda: AutoSliceDecisionEngine().apply(document, optimization, target, profile),
            )
        )
        translated_source = optimized or document
        translation = measure(
            "translation_plan",
            lambda: build_translation_plan(translated_source, SlicerType(context.target_slicer)),
        )
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
            for item in optimization.changes
        )
        report = TranslationReport(
            translation.operations + optimization_items
        ).with_weighted_score()
        return PipelineSnapshot(
            document,
            optimized,
            target,
            project,
            printability,
            support,
            placement,
            optimization,
            translation,
            report,
            tuple(stages),
            analyze_only,
        )
