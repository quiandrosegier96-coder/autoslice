from math import nan

from app.threemf.domain.build import Build, BuildItem
from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.geometry import Mesh, ModelObject, Triangle
from app.threemf.domain.metadata import PackageInfo, SlicerType, SourceInfo
from app.threemf.domain.settings import ConversionMode
from app.threemf.intelligence.analyzer import ProjectAnalyzer
from app.threemf.intelligence.engine import AutoSliceDecisionEngine
from app.threemf.intelligence.geometry import GeometryAnalyzer, PrintabilityStatus, validate_mesh
from app.threemf.intelligence.models import AutoSliceProfile, Confidence, OrientationMode
from app.threemf.intelligence.profiles import build_target_profile


def box(x, y, z, offset=(0, 0, 0)):
    ox, oy, oz = offset
    v = tuple(
        (ox + a, oy + b, oz + c)
        for a, b, c in (
            (0, 0, 0),
            (x, 0, 0),
            (x, y, 0),
            (0, y, 0),
            (0, 0, z),
            (x, 0, z),
            (x, y, z),
            (0, y, z),
        )
    )
    faces = (
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
    return Mesh(v, tuple(Triangle(face) for face in faces))


def document(*meshes):
    objects = tuple(ModelObject(str(i + 1), mesh=mesh) for i, mesh in enumerate(meshes))
    return Universal3MFDocument(
        "1",
        SourceInfo(SlicerType.CORE, confidence=1),
        PackageInfo("3D/3dmodel.model"),
        objects=objects,
        build=Build(tuple(BuildItem(o.object_id) for o in objects)),
    )


def target():
    return build_target_profile("anycubic", "kobra_s1_combo", 0.4, "pla")


def test_valid_flat_box_stays_flat():
    report = GeometryAnalyzer().analyze(document(box(40, 30, 5)), target(), AutoSliceProfile())
    assert report.status is PrintabilityStatus.GOOD
    assert report.objects[0].orientation.rotation_degrees == (0.0, 0.0, 0.0)


def test_vertical_object_gets_orientation_recommendation():
    report = GeometryAnalyzer().analyze(document(box(5, 8, 80)), target(), AutoSliceProfile())
    assert report.objects[0].orientation.candidates
    assert report.objects[0].orientation.rotation_degrees != (0.0, 0.0, 0.0)


def test_equal_candidates_have_low_confidence():
    report = GeometryAnalyzer().analyze(document(box(20, 20, 20)), target(), AutoSliceProfile())
    assert report.objects[0].orientation.confidence.value == "low"


def test_invalid_mesh_is_blocked():
    health = validate_mesh(Mesh(((0, 0, 0), (nan, 0, 0)), (Triangle((0, 1, 9)),)))
    assert health.status is PrintabilityStatus.BLOCKED


def test_collision_and_thin_feature_warnings():
    report = GeometryAnalyzer().analyze(
        document(box(0.1, 10, 10), box(5, 5, 5)), target(), AutoSliceProfile()
    )
    assert report.collisions[0].kind == "OBJECT_COLLISION"
    assert report.objects[0].thin_feature_status == "LIKELY_UNPRINTABLE"
    assert report.status is PrintabilityStatus.WARNING


def test_outside_build_volume_is_blocked():
    report = GeometryAnalyzer().analyze(document(box(260, 20, 20)), target(), AutoSliceProfile())
    assert report.project_build_volume == "PROJECT_DOES_NOT_FIT"
    assert report.status is PrintabilityStatus.BLOCKED


def test_preserve_never_applies_geometry_change():
    doc = document(box(5, 8, 80))
    profile = AutoSliceProfile(orientation_mode=OrientationMode.PRESERVE)
    engine = AutoSliceDecisionEngine()
    plan = engine.evaluate(
        doc, ProjectAnalyzer().analyze(doc, target()), target(), ConversionMode.PRESERVE, profile
    )
    assert all(not change.applied for change in plan.geometry_changes)
    assert engine.apply(doc, plan, target(), profile) == doc


def test_autoslice_applies_only_high_confidence_safe_rotation():
    doc = document(box(5, 8, 80))
    t = target()
    profile = AutoSliceProfile(
        orientation_improvement_threshold=5,
        orientation_confidence_threshold=Confidence.LOW,
    )
    engine = AutoSliceDecisionEngine()
    plan = engine.evaluate(doc, ProjectAnalyzer().analyze(doc, t), t, profile=profile)
    assert plan.geometry_changes and plan.geometry_changes[0].applied
    optimized = engine.apply(doc, plan, t, profile)
    assert (
        optimized.build.items[0].transform.values == plan.geometry_changes[0].recommended_transform
    )


def test_rotation_never_bypasses_fit_or_multi_object_collision():
    t = target()
    engine = AutoSliceDecisionEngine()
    too_large = document(box(260, 20, 20))
    blocked = engine.evaluate(too_large, ProjectAnalyzer().analyze(too_large, t), t)
    assert blocked.blocked and not any(change.applied for change in blocked.geometry_changes)
    colliding = document(box(5, 8, 80), box(10, 10, 10))
    multi = engine.evaluate(colliding, ProjectAnalyzer().analyze(colliding, t), t)
    assert multi.geometry_changes == ()


def test_deterministic_geometry_and_plan():
    doc = document(box(5, 8, 80))
    t = target()
    profile = AutoSliceProfile()
    analyzer = GeometryAnalyzer()
    engine = AutoSliceDecisionEngine()
    reports = [analyzer.analyze(doc, t, profile) for _ in range(3)]
    plans = [
        engine.evaluate(doc, ProjectAnalyzer().analyze(doc, t), t, profile=profile)
        for _ in range(3)
    ]
    assert [report.objects for report in reports] == [reports[0].objects] * 3
    assert plans == [plans[0]] * 3
