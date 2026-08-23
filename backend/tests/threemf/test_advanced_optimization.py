from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.geometry import Mesh, ModelObject, Triangle
from app.threemf.domain.metadata import PackageInfo, SlicerType, SourceInfo
from app.threemf.domain.settings import PrintSettings
from app.threemf.intelligence.analyzer import ProjectAnalyzer
from app.threemf.intelligence.engine import AutoSliceDecisionEngine
from app.threemf.intelligence.optimization import (
    AdvancedPrintOptimizationEngine,
    ObjectiveWeights,
    OptimizationProfile,
)
from app.threemf.intelligence.profiles import build_target_profile


def document(layer=0.2, walls=3, infill=20, speed=100, temp=210):
    mesh = Mesh(
        ((0, 0, 0), (20, 0, 0), (0, 20, 0), (0, 0, 20)),
        (Triangle((0, 2, 1)), Triangle((0, 1, 3)), Triangle((0, 3, 2)), Triangle((1, 2, 3))),
    )
    return Universal3MFDocument(
        "1",
        SourceInfo(SlicerType.CORE, confidence=1),
        PackageInfo("3D/3dmodel.model"),
        objects=(ModelObject("1", mesh=mesh),),
        process=PrintSettings(
            layer_height_mm=layer,
            wall_count=walls,
            infill_density_percent=infill,
            print_speed_mm_s=speed,
            nozzle_temperature_c=temp,
            bed_temperature_c=60,
            fan_speed_percent=100,
        ),
    )


def target():
    return build_target_profile("anycubic", "kobra_s1_combo", 0.4, "pla")


def selected(profile):
    return AdvancedPrintOptimizationEngine().optimize(document(), target(), profile).selected


def test_balanced_profile_selects_viable_candidate():
    assert selected(OptimizationProfile.BALANCED).viable


def test_quality_profile_prefers_smaller_layers_and_more_walls():
    values = dict(selected(OptimizationProfile.QUALITY).settings)
    assert values["layer_height_mm"] <= 0.2 and values["wall_count"] >= 3


def test_fast_profile_prefers_speed_and_thicker_layer():
    values = dict(selected(OptimizationProfile.FAST).settings)
    assert values["print_speed_mm_s"] >= 100 and values["layer_height_mm"] >= 0.2


def test_material_saving_profile_reduces_infill_and_walls():
    values = dict(selected(OptimizationProfile.MATERIAL_SAVING).settings)
    assert values["infill_density_percent"] <= 10 and values["wall_count"] <= 2


def test_custom_objective_weights_are_validated():
    weights = ObjectiveWeights(
        (("quality", 1.0), ("reliability", 0.0), ("speed", 0.0), ("material", 0.0))
    )
    result = AdvancedPrintOptimizationEngine().optimize(document(), target(), weights=weights)
    assert result.weights == weights


def test_hard_limits_make_every_candidate_non_viable():
    result = AdvancedPrintOptimizationEngine().optimize(document(), target(), hard_blocked=True)
    assert all(
        not item.viable and "PROJECT_HARD_LIMIT" in item.hard_limit_violations
        for item in result.candidates
    )


def test_hard_rule_wins_conflict_with_objective_candidate():
    doc = document(layer=0.5)
    t = target()
    plan = AutoSliceDecisionEngine().evaluate(doc, ProjectAnalyzer().analyze(doc, t), t)
    change = plan.change_for("layer_height_mm")
    assert (
        change.rule == "NOZZLE_LAYER_HEIGHT_RANGE"
        and change.new_value <= t.nozzle.maximum_layer_height_mm
    )


def test_analyze_only_produces_preview_without_mutation():
    doc = document()
    result = AdvancedPrintOptimizationEngine().optimize(
        doc, target(), OptimizationProfile.FAST, analyze_only=True
    )
    assert result.analyze_only and doc.process.layer_height_mm == 0.2 and result.explanations


def test_optimization_is_deterministic_except_benchmark():
    engine = AdvancedPrintOptimizationEngine()
    results = [engine.optimize(document(), target(), OptimizationProfile.QUALITY) for _ in range(3)]
    assert [r.selected for r in results] == [results[0].selected] * 3
    assert [r.explanations for r in results] == [results[0].explanations] * 3


def test_optimization_benchmark_is_recorded():
    result = AdvancedPrintOptimizationEngine().optimize(document(), target())
    assert 0 <= result.benchmark_ms < 100
