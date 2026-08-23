import dataclasses

import pytest

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.conversion import create_conversion_service
from app.threemf.domain.settings import ConversionContext, ConversionMode
from app.threemf.parsers import default_parser_registry
from app.threemf.pipeline.orchestrator import FullUniversal3MFPipeline
from app.threemf.translation.engine import AutoSliceTranslationEngine


def context(mode=ConversionMode.AUTOSLICE):
    return ConversionContext("anycubic", "kobra_s1_combo", 0.4, "pla", mode)


def document(payload):
    return default_parser_registry().parse(ThreeMFContainer.from_bytes(payload))


def test_analyze_only_builds_complete_snapshot_without_applying(core_3mf_bytes):
    source = document(core_3mf_bytes)
    snapshot = FullUniversal3MFPipeline().analyze(source, context(), analyze_only=True)
    assert snapshot.source_document is source and snapshot.optimized_document is None
    assert (
        snapshot.project
        and snapshot.printability
        and snapshot.support_plan
        and snapshot.placement_plan
    )
    assert snapshot.optimization_plan and snapshot.translation_plan and snapshot.translation_report
    assert [stage.name for stage in snapshot.stages] == [
        "target_profile",
        "project_analysis",
        "geometry_printability",
        "support_analysis",
        "placement_analysis",
        "optimization",
        "translation_plan",
    ]


def test_execution_applies_exact_snapshot_plan_before_translation(core_3mf_bytes):
    source = document(core_3mf_bytes)
    snapshot = FullUniversal3MFPipeline().analyze(source, context(), analyze_only=False)
    assert snapshot.optimized_document is not None
    assert [stage.name for stage in snapshot.stages][-2:] == ["apply_reanalyze", "translation_plan"]
    assert snapshot.translation_plan.source == source.source.slicer


def test_preserve_runs_pipeline_without_mutating_document(core_3mf_bytes):
    source = document(core_3mf_bytes)
    outcome = AutoSliceTranslationEngine().translate(source, context(ConversionMode.PRESERVE))
    assert outcome.document is source
    assert outcome.pipeline_snapshot and outcome.pipeline_snapshot.optimization_plan.changes == ()


def test_pipeline_semantics_are_deterministic(core_3mf_bytes):
    source = document(core_3mf_bytes)
    snapshots = [
        FullUniversal3MFPipeline().analyze(source, context(), analyze_only=True) for _ in range(3)
    ]
    assert [item.optimization_plan for item in snapshots] == [snapshots[0].optimization_plan] * 3
    assert [item.translation_plan for item in snapshots] == [snapshots[0].translation_plan] * 3


def test_pipeline_rejects_missing_target_profile(core_3mf_bytes):
    with pytest.raises(ValueError, match="target printer"):
        FullUniversal3MFPipeline().analyze(document(core_3mf_bytes), ConversionContext("anycubic"))


def test_production_service_returns_valid_download_and_stage_observability(three_mf_factory):
    source = three_mf_factory({"Metadata/BambuStudio.config": b"{}"})
    result = create_conversion_service().convert_3mf(
        source, context(), original_filename="pipeline.3mf"
    )
    assert result.output_filename == "pipeline_AutoSlice.3mf"
    assert result.pipeline_stages
    assert [name for name, _, status in result.pipeline_stages if status == "completed"][
        -1
    ] == "translation_plan"


def test_snapshot_is_machine_serializable(core_3mf_bytes):
    snapshot = FullUniversal3MFPipeline().analyze(
        document(core_3mf_bytes), context(), analyze_only=True
    )
    payload = dataclasses.asdict(snapshot)
    assert payload["optimization_plan"] and payload["stages"]
