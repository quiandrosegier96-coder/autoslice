from dataclasses import replace

import pytest

from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.geometry import Mesh, ModelObject, Triangle
from app.threemf.domain.materials import Material
from app.threemf.domain.metadata import PackageInfo, SlicerType, SourceInfo
from app.threemf.domain.settings import ConversionMode, PrintSettings
from app.threemf.intelligence.analyzer import ProjectAnalyzer
from app.threemf.intelligence.engine import AutoSliceDecisionEngine
from app.threemf.intelligence.models import (
    Confidence,
    OptimizationChange,
    OptimizationPlan,
    PlanStatus,
    RulePriority,
)
from app.threemf.intelligence.profiles import build_target_profile


def _document(*, size=20.0, layer=0.2, temperature=205, material="pla"):
    vertices = ((0, 0, 0), (size, 0, 0), (0, size, 0), (0, 0, size))
    triangles = (Triangle((0, 2, 1)), Triangle((0, 1, 3)), Triangle((0, 3, 2)), Triangle((1, 2, 3)))
    return Universal3MFDocument(
        "1.0",
        SourceInfo(SlicerType.BAMBU, confidence=1.0),
        PackageInfo("3D/3dmodel.model"),
        objects=(ModelObject("1", mesh=Mesh(vertices, triangles), material_resource_id="m1"),),
        process=PrintSettings(
            layer_height_mm=layer,
            nozzle_temperature_c=temperature,
            wall_count=3,
            infill_density_percent=15,
        ),
        materials=(Material("m1", filament_type=material),),
    )


@pytest.fixture
def target():
    return build_target_profile("anycubic", "kobra_s1_combo", 0.4, "pla")


def test_build_volume_rule(target):
    document = _document(size=260)
    analysis = ProjectAnalyzer().analyze(document, target)
    plan = AutoSliceDecisionEngine().evaluate(document, analysis, target)
    assert analysis.build_volume_status is PlanStatus.OUTSIDE_BUILD_VOLUME
    assert plan.blocked[0].rule == "BUILD_VOLUME_LIMIT"
    assert not plan.can_convert


def test_layer_height_rule_and_nozzle_compatibility(target):
    document = _document(layer=0.32)
    plan = AutoSliceDecisionEngine().evaluate(
        document, ProjectAnalyzer().analyze(document, target), target
    )
    change = plan.change_for("layer_height_mm")
    assert change and change.new_value == 0.2
    assert change.rule == "NOZZLE_LAYER_HEIGHT_RANGE"
    assert change.confidence is Confidence.HIGH


def test_material_compatibility(target):
    document = _document(material="petg")
    plan = AutoSliceDecisionEngine().evaluate(
        document, ProjectAnalyzer().analyze(document, target), target
    )
    assert any(item.code == "SOURCE_TARGET_MATERIAL_MISMATCH" for item in plan.warnings)


def test_preserve_mode_does_not_apply_changes(target):
    document = _document(layer=0.32)
    engine = AutoSliceDecisionEngine()
    plan = engine.evaluate(
        document, ProjectAnalyzer().analyze(document, target), target, ConversionMode.PRESERVE
    )
    assert plan.changes == ()
    assert engine.apply(document, plan) == document
    assert any(item.rule == "NOZZLE_LAYER_HEIGHT_RANGE" for item in plan.recommendations)


def test_autoslice_mode_applies_traceable_change(target):
    document = _document(layer=0.32)
    engine = AutoSliceDecisionEngine()
    plan = engine.evaluate(document, ProjectAnalyzer().analyze(document, target), target)
    optimized = engine.apply(document, plan)
    assert optimized.process.layer_height_mm == 0.2
    assert plan.changes[0].old_value == 0.32
    assert plan.changes[0].reason and plan.changes[0].rule and plan.changes[0].confidence


def test_rule_priority_and_conflict_are_deterministic():
    low = OptimizationChange(
        "layer_height_mm",
        0.3,
        0.2,
        "quality",
        "Z_RULE",
        Confidence.MEDIUM,
        RulePriority.QUALITY,
        "quality",
    )
    high = replace(
        low, new_value=0.24, reason="limit", rule="A_RULE", priority=RulePriority.HARD_LIMIT
    )
    candidates = sorted(
        (low, high), key=lambda item: (item.setting, -int(item.priority), item.rule)
    )
    assert candidates[0] == high


def test_optimization_plan_shape_and_compatibility(target):
    document = _document()
    plan = AutoSliceDecisionEngine().evaluate(
        document, ProjectAnalyzer().analyze(document, target), target
    )
    assert isinstance(plan, OptimizationPlan)
    assert plan.can_convert
    assert 0 <= plan.compatibility.final_compatibility <= 100


def test_deterministic_output(target):
    document = _document(layer=0.32, temperature=180)
    analyzer = ProjectAnalyzer()
    engine = AutoSliceDecisionEngine()
    outputs = [
        engine.evaluate(document, analyzer.analyze(document, target), target) for _ in range(5)
    ]
    assert outputs == [outputs[0]] * 5


def test_blocked_plan_cannot_be_applied(target):
    document = _document(size=260)
    engine = AutoSliceDecisionEngine()
    plan = engine.evaluate(document, ProjectAnalyzer().analyze(document, target), target)
    with pytest.raises(ValueError, match="blocked"):
        engine.apply(document, plan)
