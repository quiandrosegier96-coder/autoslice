from pathlib import Path

from app.threemf.capabilities import FeatureSupport, capabilities_for, target_capabilities_for
from app.threemf.container.reader import ThreeMFContainer
from app.threemf.detection import detect_3mf
from app.threemf.domain.metadata import SlicerType
from app.threemf.parsers import default_parser_registry
from app.threemf.parsers.bambu import BambuParser
from app.threemf.parsers.cura import CuraParser
from app.threemf.parsers.orca import OrcaParser
from app.threemf.parsers.prusa import PrusaParser

CURA_MODEL = b'''<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><metadata name="Application">Ultimaker Cura 5.x</metadata><resources><object id="1" name="Part A" type="model"><mesh><vertices><vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/><vertex x="0" y="1" z="0"/></vertices><triangles><triangle v1="0" v2="1" v3="2"/></triangles></mesh></object><object id="2" name="Part B" type="model"><components><component objectid="1" transform="1 0 0 0 1 0 0 0 1 10 0 0"/></components></object></resources><build><item objectid="2" transform="1 0 0 0 1 0 0 0 1 20 0 0"/></build></model>'''
CURA_METADATA = b'''<cura><metadata name="layer_height" value="0.16"/><metadata name="layer_height_0" value="0.24"/><metadata name="wall_line_count" value="4"/><metadata name="infill_sparse_density" value="20"/><metadata name="speed_print" value="60"/><metadata name="material_print_temperature" value="215"/><metadata name="support_enable" value="true"/><metadata name="future_cura_setting" value="opaque"/><object id="1"><setting key="extruder_nr" value="1"/><setting key="mesh_type" value="infill_mesh"/></object></cura>'''


def _cura(three_mf_factory):
    return ThreeMFContainer.from_bytes(three_mf_factory({"Metadata/cura.xml": CURA_METADATA}, model_xml=CURA_MODEL), "cura.3mf")


def test_cura_detection_requires_multiple_signals(three_mf_factory):
    neutral = b'<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><resources/><build/></model>'
    marker_only = ThreeMFContainer.from_bytes(three_mf_factory({"Metadata/Cura.config": b"{}"}, model_xml=neutral))
    assert detect_3mf(marker_only).slicer is SlicerType.UNKNOWN
    result = detect_3mf(_cura(three_mf_factory))
    assert result.slicer is SlicerType.CURA
    assert result.confidence >= 0.9
    assert len(result.evidence) >= 2


def test_cura_is_not_other_source_families(three_mf_factory):
    container = _cura(three_mf_factory)
    assert BambuParser().can_parse(container).confidence == 0
    assert OrcaParser().can_parse(container).confidence == 0
    assert PrusaParser().can_parse(container).confidence == 0


def test_cura_parser_preserves_scene_and_maps_explicit_semantics(three_mf_factory):
    document = CuraParser().parse(_cura(three_mf_factory))
    assert [obj.object_id for obj in document.objects] == ["1", "2"]
    assert document.objects[1].components[0].object_id == "1"
    assert document.build.items[0].object_id == "2"
    assert document.process.layer_height_mm == 0.16
    assert document.process.first_layer_height_mm == 0.24
    assert document.process.wall_count == 4
    assert document.process.infill_density_percent == 20
    assert document.supports.enabled is True
    assert document.objects[0].role.value == "modifier"
    assert document.objects[0].material_resource_id == "cura-extruder:1"
    assert document.tool_assignments[0].tool_index == 1
    assert any(key == "future_cura_setting" for key, _ in document.process.source_values)
    assert any(item.path == "Metadata/cura.xml" for item in document.resources.opaque)


def test_registry_and_capabilities_are_conservative(three_mf_factory):
    document = default_parser_registry().parse(_cura(three_mf_factory))
    assert document.source.slicer is SlicerType.CURA
    assert capabilities_for(SlicerType.CURA).for_feature("print_settings").support is FeatureSupport.SUPPORTED_WITH_LIMITS
    assert target_capabilities_for(SlicerType.CURA).capabilities == ()


def test_anycubic_exporter_has_no_cura_source_dependency():
    exporter = Path(__file__).parents[2] / "app" / "threemf" / "exporters" / "anycubic_native.py"
    assert "cura" not in exporter.read_text(encoding="utf-8").lower()
