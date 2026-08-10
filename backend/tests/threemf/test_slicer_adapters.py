from app.threemf.container.reader import ThreeMFContainer
from app.threemf.domain.metadata import SlicerType
from app.threemf.parsers.anycubic import AnycubicParser
from app.threemf.parsers.bambu import BambuParser

PROJECT = b'{"layer_height":"0.2","wall_loops":"3","filament_colour":["#112233"],"filament_type":["PLA"],"filament_settings_id":["Generic PLA"],"filament_diameter":["1.75"]}'
MODEL_SETTINGS = b'<config><object id="1"><metadata key="extruder" value="1"/></object></config>'


def test_bambu_adapter_maps_known_settings_and_explicit_material(three_mf_factory):
    payload = three_mf_factory({"Metadata/BambuStudio.config": b"{}", "Metadata/project_settings.config": PROJECT, "Metadata/model_settings.config": MODEL_SETTINGS})
    document = BambuParser().parse(ThreeMFContainer.from_bytes(payload))
    assert document.source.slicer is SlicerType.BAMBU
    assert document.process.layer_height_mm == 0.2
    assert document.process.wall_count == 3
    assert document.objects[0].material_resource_id == "filament-slot:1"
    assert document.tool_assignments[0].material_id == "filament-slot:1"


def test_anycubic_adapter_preserves_object_identity(three_mf_factory):
    payload = three_mf_factory({"Metadata/AnycubicSlicer.config": b"{}", "Metadata/project_settings.config": PROJECT})
    document = AnycubicParser().parse(ThreeMFContainer.from_bytes(payload))
    assert document.source.slicer is SlicerType.ANYCUBIC
    assert [obj.object_id for obj in document.objects] == ["1", "2"]
    assert document.objects[1].components[0].object_id == "1"
    assert document.build.items[0].object_id == "2"


def test_no_material_is_invented_without_explicit_object_mapping(three_mf_factory):
    payload = three_mf_factory({"Metadata/AnycubicSlicer.config": b"{}", "Metadata/project_settings.config": PROJECT})
    document = AnycubicParser().parse(ThreeMFContainer.from_bytes(payload))
    assert document.objects[1].material_resource_id is None
