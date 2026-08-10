from pathlib import Path

from app.threemf.capabilities import FeatureSupport, capabilities_for
from app.threemf.container.reader import ThreeMFContainer
from app.threemf.detection import detect_3mf
from app.threemf.domain.metadata import SlicerType
from app.threemf.parsers import default_parser_registry
from app.threemf.parsers.bambu import BambuParser
from app.threemf.parsers.orca import OrcaParser

PROJECT = b'{"layer_height":"0.16","wall_loops":"4","sparse_infill_density":"20%","filament_colour":["#334455"],"filament_type":["PETG"],"filament_settings_id":["Orca PETG"],"filament_diameter":["1.75"],"orca_future_setting":{"value":1}}'


def test_explicit_orca_marker_is_not_detected_as_bambu(three_mf_factory):
    payload = three_mf_factory({"Metadata/OrcaSlicer.config": b"{}", "Metadata/project_settings.config": PROJECT})
    container = ThreeMFContainer.from_bytes(payload)
    detection = detect_3mf(container)
    assert detection.slicer is SlicerType.ORCA
    assert detection.confidence >= 0.8
    assert detection.evidence
    assert BambuParser().can_parse(container).confidence == 0


def test_bambu_marker_is_not_detected_as_orca(three_mf_factory):
    container = ThreeMFContainer.from_bytes(three_mf_factory({"Metadata/BambuStudio.config": b"{}"}))
    assert detect_3mf(container).slicer is SlicerType.BAMBU
    assert OrcaParser().can_parse(container).confidence == 0


def test_orca_application_metadata_detects_version_evidence(three_mf_factory):
    model = b'<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><metadata name="Application">OrcaSlicer 2.x</metadata><resources/><build/></model>'
    result = detect_3mf(ThreeMFContainer.from_bytes(three_mf_factory(model_xml=model)))
    assert result.slicer is SlicerType.ORCA
    assert result.version == "OrcaSlicer 2.x"
    assert result.evidence


def test_orca_parser_preserves_objects_build_settings_and_opaque(three_mf_factory):
    payload = three_mf_factory({
        "Metadata/OrcaSlicer.config": b"{}", "Metadata/project_settings.config": PROJECT,
        "Metadata/orca_custom.config": b"opaque-orca-payload",
    })
    document = OrcaParser().parse(ThreeMFContainer.from_bytes(payload, "orca.3mf"))
    assert [obj.object_id for obj in document.objects] == ["1", "2"]
    assert document.objects[1].components[0].object_id == "1"
    assert document.build.items[0].object_id == "2"
    assert document.process.layer_height_mm == 0.16
    assert document.process.wall_count == 4
    assert document.process.source_values
    assert any(item.path == "Metadata/orca_custom.config" for item in document.resources.opaque)


def test_default_registry_selects_orca_adapter(three_mf_factory):
    payload = three_mf_factory({"Metadata/OrcaSlicer.config": b"{}", "Metadata/project_settings.config": PROJECT})
    document = default_parser_registry().parse(ThreeMFContainer.from_bytes(payload))
    assert document.source.slicer is SlicerType.ORCA


def test_orca_capabilities_do_not_claim_unverified_plate_or_painting_support():
    profile = capabilities_for(SlicerType.ORCA)
    assert profile.for_feature("multiple_plates").support is FeatureSupport.PRESERVED_OPAQUE
    assert profile.for_feature("color_painting").support is FeatureSupport.PRESERVED_OPAQUE


def test_anycubic_exporter_has_no_orca_source_dependency():
    exporter = Path(__file__).parents[2] / "app" / "threemf" / "exporters" / "anycubic_native.py"
    assert "orca" not in exporter.read_text(encoding="utf-8").lower()
