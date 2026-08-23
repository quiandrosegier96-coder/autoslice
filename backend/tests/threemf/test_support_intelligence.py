from app.threemf.domain.build import Build, BuildItem
from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.geometry import Mesh, ModelObject, Triangle
from app.threemf.domain.metadata import PackageInfo, SlicerType, SourceInfo
from app.threemf.domain.settings import ConversionMode
from app.threemf.domain.supports import SupportConfig
from app.threemf.domain.supports import SupportRegion as SourceSupportRegion
from app.threemf.intelligence.analyzer import ProjectAnalyzer
from app.threemf.intelligence.engine import AutoSliceDecisionEngine
from app.threemf.intelligence.geometry import GeometryAnalyzer
from app.threemf.intelligence.models import AutoSliceProfile
from app.threemf.intelligence.profiles import build_target_profile
from app.threemf.intelligence.support import SupportAnalyzer, SupportStrategy


def mesh_with_overhangs(count=1):
    vertices = [(0, 0, 0)]
    triangles = []
    for index in range(count):
        x = index * 20
        start = len(vertices)
        vertices.extend(((x, 0, 10), (x, 10, 10), (x + 10, 0, 10)))
        triangles.append(Triangle((start, start + 1, start + 2)))  # downward normal
    return Mesh(tuple(vertices), tuple(triangles))


def cube():
    v = (
        (0, 0, 0),
        (10, 0, 0),
        (10, 10, 0),
        (0, 10, 0),
        (0, 0, 10),
        (10, 0, 10),
        (10, 10, 10),
        (0, 10, 10),
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


def moderate_overhang():
    return Mesh(((0, 0, 0), (0, 0, 10), (0, 10, 10), (10, 0, 15.77)), (Triangle((1, 2, 3)),))


def doc(mesh, supports=SupportConfig()):
    obj = ModelObject("1", mesh=mesh)
    return Universal3MFDocument(
        "1",
        SourceInfo(SlicerType.CORE, confidence=1),
        PackageInfo("3D/3dmodel.model"),
        objects=(obj,),
        build=Build((BuildItem("1"),)),
        supports=supports,
    )


def target():
    return build_target_profile("anycubic", "kobra_s1_combo", 0.4, "pla")


def plan(document, mode=ConversionMode.AUTOSLICE):
    geometry = GeometryAnalyzer().analyze(document, target(), AutoSliceProfile())
    return SupportAnalyzer().analyze(document, geometry, target(), mode)


def test_cube_needs_no_support():
    result = plan(doc(cube()))
    assert result.strategy is SupportStrategy.NONE
    assert result.diagnostics[0].code == "SUPPORT_NOT_REQUIRED"


def test_extreme_overhang_creates_required_region():
    result = plan(doc(mesh_with_overhangs()))
    assert len(result.required_regions) == 1
    assert result.required_regions[0].severity == "critical"
    assert result.applied


def test_moderate_overhang_is_optional_recommendation():
    result = plan(doc(moderate_overhang()))
    assert len(result.optional_regions) == 1
    assert result.optional_regions[0].severity == "moderate"
    assert result.diagnostics[-1].code == "SUPPORT_RECOMMENDED"


def test_multiple_disconnected_overhangs_create_regions():
    result = plan(doc(mesh_with_overhangs(2)))
    assert len(result.required_regions) == 2
    assert result.estimated_support_volume_mm3 > 0


def test_blocker_creates_conflict_and_blocks_region():
    supports = SupportConfig(regions=(SourceSupportRegion("1", "support_blocker"),))
    result = plan(doc(mesh_with_overhangs(), supports))
    assert result.blocked_regions and not result.applied
    assert any(item.code == "SUPPORT_CONFLICT" for item in result.diagnostics)


def test_enforcer_creates_required_region_without_overhang():
    supports = SupportConfig(regions=(SourceSupportRegion("1", "support_enforcer"),))
    result = plan(doc(cube(), supports))
    assert result.required_regions[0].enforced_by_source


def test_preserve_mode_never_applies_support_plan():
    result = plan(doc(mesh_with_overhangs()), ConversionMode.PRESERVE)
    assert result.required_regions and not result.applied and result.preserves_source_supports


def test_autoslice_support_change_is_traceable_and_applied():
    document = doc(mesh_with_overhangs())
    t = target()
    engine = AutoSliceDecisionEngine()
    optimization = engine.evaluate(document, ProjectAnalyzer().analyze(document, t), t)
    assert optimization.support_changes
    change = optimization.support_changes[0]
    assert (
        change.old_value is None
        and change.new_value is True
        and change.reason
        and change.rule
        and change.confidence
    )
    optimized = engine.apply(document, optimization, t)
    assert optimized.supports.enabled is True
    assert optimized.supports.support_type == "tree"


def test_support_plan_is_deterministic():
    document = doc(mesh_with_overhangs(2))
    assert [plan(document) for _ in range(3)] == [plan(document)] * 3
