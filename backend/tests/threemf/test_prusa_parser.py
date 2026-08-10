from pathlib import Path

from app.threemf.capabilities import FeatureSupport, capabilities_for
from app.threemf.container.reader import ThreeMFContainer
from app.threemf.detection import detect_3mf
from app.threemf.domain.metadata import SlicerType
from app.threemf.parsers import default_parser_registry
from app.threemf.parsers.bambu import BambuParser
from app.threemf.parsers.orca import OrcaParser
from app.threemf.parsers.prusa import PrusaParser

PRUSA_MODEL = b'''<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><metadata name="Application">PrusaSlicer 2.9</metadata><resources><object id="1" name="Part A" type="model"><mesh><vertices><vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/><vertex x="0" y="1" z="0"/></vertices><triangles><triangle v1="0" v2="1" v3="2"/></triangles></mesh></object><object id="2" name="Assembly" type="model"><components><component objectid="1" transform="1 0 0 0 1 0 0 0 1 10 0 0"/></components></object></resources><build><item objectid="2" transform="1 0 0 0 1 0 0 0 1 20 0 0"/></build></model>'''
PRUSA_SETTINGS = b'{"layer_height":"0.15","first_layer_height":"0.2","perimeters":"4","top_solid_layers":"5","bottom_solid_layers":"4","fill_density":"18%","fill_pattern":"gyroid","perimeter_speed":"45","temperature":["215"],"filament_colour":["#AA5500"],"filament_type":["PETG"],"filament_settings_id":["Prusament PETG"],"prusa_future_key":{"kept":true}}'


def _prusa(three_mf_factory, extra=None):
    parts = {"Metadata/PrusaSlicer.config": b"{}", "Metadata/project_settings.config": PRUSA_SETTINGS}
    parts.update(extra or {})
    return ThreeMFContainer.from_bytes(three_mf_factory(parts, model_xml=PRUSA_MODEL), "prusa.3mf")


def test_prusa_detection_requires_multiple_signals(three_mf_factory):
    neutral_model = b'<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><resources/><build/></model>'
    marker_only = ThreeMFContainer.from_bytes(three_mf_factory({"Metadata/PrusaSlicer.config": b"{}"}, model_xml=neutral_model))
    assert detect_3mf(marker_only).slicer is SlicerType.UNKNOWN
    result = detect_3mf(_prusa(three_mf_factory))
    assert result.slicer is SlicerType.PRUSA
    assert result.confidence >= 0.9
    assert len(result.evidence) >= 2


def test_prusa_is_not_bambu_or_orca(three_mf_factory):
    container = _prusa(three_mf_factory)
    assert BambuParser().can_parse(container).confidence == 0
    assert OrcaParser().can_parse(container).confidence == 0


def test_prusa_parser_preserves_core_scene_and_maps_semantics(three_mf_factory):
    document = PrusaParser().parse(_prusa(three_mf_factory, {"Metadata/prusa_custom.ini": b"opaque"}))
    assert [obj.object_id for obj in document.objects] == ["1", "2"]
    assert document.objects[1].components[0].object_id == "1"
    assert document.build.items[0].object_id == "2"
    assert document.process.layer_height_mm == 0.15
    assert document.process.first_layer_height_mm == 0.2
    assert document.process.wall_count == 4
    assert document.process.infill_density_percent == 18
    assert document.process.infill_pattern == "gyroid"
    assert document.materials[-1].filament_type == "PETG"
    assert any(key == "prusa_future_key" for key, _ in document.process.source_values)
    assert any(item.path == "Metadata/prusa_custom.ini" for item in document.resources.opaque)


def test_registry_selects_prusa_and_capabilities_are_conservative(three_mf_factory):
    document = default_parser_registry().parse(_prusa(three_mf_factory))
    assert document.source.slicer is SlicerType.PRUSA
    profile = capabilities_for(SlicerType.PRUSA)
    assert profile.for_feature("print_settings").support is FeatureSupport.SUPPORTED_WITH_LIMITS
    assert profile.for_feature("multiple_plates").support is FeatureSupport.PRESERVED_OPAQUE


def test_prusa_native_metadata_config_maps_semantic_aliases(three_mf_factory):
    native = b'<config><metadata key="layer_height" value="0.12"/><metadata key="perimeters" value="5"/><metadata key="fill_density" value="22%"/><metadata key="future_native_key" value="kept"/></config>'
    payload = three_mf_factory({"Metadata/Slic3r_PE.config": native}, model_xml=PRUSA_MODEL)
    document = PrusaParser().parse(ThreeMFContainer.from_bytes(payload))
    assert document.process.layer_height_mm == 0.12
    assert document.process.wall_count == 5
    assert document.process.infill_density_percent == 22
    assert any(key == "future_native_key" for key, _ in document.process.source_values)


def test_anycubic_exporter_has_no_prusa_source_dependency():
    exporter = Path(__file__).parents[2] / "app" / "threemf" / "exporters" / "anycubic_native.py"
    assert "prusa" not in exporter.read_text(encoding="utf-8").lower()
