from dataclasses import replace

from app.threemf.domain.build import Build, BuildItem, Plate
from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.geometry import Mesh, ModelObject, Transform, Triangle
from app.threemf.domain.metadata import PackageInfo, SlicerType, SourceInfo
from app.threemf.domain.settings import ConversionMode
from app.threemf.intelligence.analyzer import ProjectAnalyzer
from app.threemf.intelligence.engine import AutoSliceDecisionEngine
from app.threemf.intelligence.placement import PlacementAnalyzer
from app.threemf.intelligence.profiles import build_target_profile


def box(size=10):
    v = (
        (0, 0, 0),
        (size, 0, 0),
        (size, size, 0),
        (0, size, 0),
        (0, 0, size),
        (size, 0, size),
        (size, size, size),
        (0, size, size),
    )
    f = (
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    )
    return Mesh(v, tuple(Triangle(x) for x in f))


def transform(x=0, y=0, z=0):
    return Transform((1, 0, 0, 0, 1, 0, 0, 0, 1, x, y, z))


def document(count=1, size=10, positions=None, plates=()):
    objects = tuple(ModelObject(str(i + 1), mesh=box(size)) for i in range(count))
    positions = positions or [(0, 0, 0)] * count
    items = tuple(
        BuildItem(obj.object_id, transform(*positions[i]), plate_id=("p1" if plates else None))
        for i, obj in enumerate(objects)
    )
    return Universal3MFDocument(
        "1",
        SourceInfo(SlicerType.CORE, confidence=1),
        PackageInfo("3D/3dmodel.model"),
        objects=objects,
        build=Build(items, plates),
    )


def target(spacing=None):
    value = build_target_profile("anycubic", "kobra_s1_combo", 0.4, "pla")
    return replace(value, printer=replace(value.printer, minimum_object_spacing_mm=spacing))


def test_single_object_stays_in_place():
    result = PlacementAnalyzer().analyze(document(), target())
    assert result.current.collision_count == 0
    assert not result.applied


def test_two_colliding_objects_get_deterministic_candidate():
    result = PlacementAnalyzer().analyze(document(2), target(), ConversionMode.AUTOSLICE)
    assert result.current.collision_count == 1
    assert result.recommended.collision_count == 0 and result.applied


def test_many_objects_use_shelf_grid_or_row_packing():
    result = PlacementAnalyzer().analyze(document(9), target(3), ConversionMode.AUTOSLICE)
    assert result.recommended.strategy in {"grid", "row", "shelf"}
    assert result.recommended.fits_build_volume


def test_profile_spacing_violation_is_repacked():
    result = PlacementAnalyzer().analyze(document(2, positions=((0, 0, 0), (12, 0, 0))), target(5))
    assert result.current.insufficient_spacing_count == 1
    assert result.recommended.insufficient_spacing_count == 0


def test_insufficient_plate_never_applies():
    result = PlacementAnalyzer().analyze(document(1, size=300), target())
    assert not result.recommended.fits_build_volume and not result.applied


def test_multiple_plates_are_preserved_conceptually():
    plates = (Plate("p1", build_item_indices=(0,)), Plate("p2", build_item_indices=(1,)))
    result = PlacementAnalyzer().analyze(document(2, plates=plates), target())
    assert len(result.plate_assignments) == 2 and not result.applied
    assert any(item.code == "MULTIPLE_PLATES_PRESERVED" for item in result.diagnostics)


def test_preserve_mode_keeps_current_transforms():
    doc = document(2)
    t = target()
    engine = AutoSliceDecisionEngine()
    plan = engine.evaluate(doc, ProjectAnalyzer().analyze(doc, t), t, ConversionMode.PRESERVE)
    assert all(not item.applied for item in plan.placement_changes)
    assert engine.apply(doc, plan, t) == doc


def test_autoslice_applies_traceable_positions_and_reanalyzes():
    doc = document(2)
    t = target(3)
    engine = AutoSliceDecisionEngine()
    plan = engine.evaluate(doc, ProjectAnalyzer().analyze(doc, t), t)
    assert plan.placement_changes and all(
        item.reason and item.rule and item.confidence for item in plan.placement_changes
    )
    optimized = engine.apply(doc, plan, t)
    checked = PlacementAnalyzer().analyze(optimized, t, ConversionMode.PRESERVE)
    assert checked.current.collision_count == 0 and checked.current.insufficient_spacing_count == 0


def test_placement_is_deterministic():
    doc = document(6)
    analyzer = PlacementAnalyzer()
    t = target(2)
    assert [analyzer.analyze(doc, t) for _ in range(3)] == [analyzer.analyze(doc, t)] * 3
