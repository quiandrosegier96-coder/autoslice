from app.threemf.container.reader import ThreeMFContainer
from app.threemf.parsers.core import CoreThreeMFParser


def test_core_parser_preserves_object_identity_components_and_build(core_3mf_bytes):
    document = CoreThreeMFParser().parse(ThreeMFContainer.from_bytes(core_3mf_bytes, "project.3mf"))
    assert [item.object_id for item in document.objects] == ["1", "2"]
    assert document.objects[1].components[0].object_id == "1"
    assert document.objects[1].components[0].transform.values[9] == 10
    assert document.build.items[0].object_id == "2"


def test_core_parser_preserves_material_and_triangle_assignment(core_3mf_bytes):
    document = CoreThreeMFParser().parse(ThreeMFContainer.from_bytes(core_3mf_bytes))
    assert document.materials[0].name == "Red PLA"
    assert document.objects[0].mesh.triangles[0].property_resource_id == "5"
