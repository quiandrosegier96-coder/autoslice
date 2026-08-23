from io import BytesIO
import zipfile
import pytest
from app.threemf.container.reader import ContainerLimits, ThreeMFContainer
from app.threemf.container.opc import primary_model_path, validate_relationships
from app.threemf.container.security import UnsafeThreeMFError
from app.threemf.container.xml import MAX_XML_BYTES, parse_xml


def test_container_is_read_only_and_lists_normalized_paths(core_3mf_bytes):
    container = ThreeMFContainer.from_bytes(core_3mf_bytes, "model.3mf")
    assert container.filename == "model.3mf"
    assert container.exists("3D/3dmodel.model")
    assert container.paths == tuple(sorted(container.paths))


def test_container_rejects_path_traversal():
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("../escape.model", b"x")
    with pytest.raises(UnsafeThreeMFError, match="Unsafe ZIP member"):
        ThreeMFContainer.from_bytes(output.getvalue())


def test_container_enforces_file_count(three_mf_factory):
    with pytest.raises(UnsafeThreeMFError, match="too many files"):
        ThreeMFContainer.from_bytes(three_mf_factory(), limits=ContainerLimits(max_files=2))


def test_xml_parser_rejects_entities():
    with pytest.raises(UnsafeThreeMFError, match="DTD/entity"):
        parse_xml(b'<!DOCTYPE model [<!ENTITY secret SYSTEM "file:///etc/passwd">]><model/>')


def test_xml_parser_rejects_oversized_parts():
    with pytest.raises(UnsafeThreeMFError, match="safety limit"):
        parse_xml(b"x" * (MAX_XML_BYTES + 1), "3D/3dmodel.model")


def test_primary_model_rejects_external_relationship():
    relationships = b'''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="https://evil.example/model" TargetMode="External" Id="r1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'''
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("_rels/.rels", relationships)
        archive.writestr("3D/3dmodel.model", b"<model/>")
    container = ThreeMFContainer.from_bytes(output.getvalue())
    with pytest.raises(UnsafeThreeMFError, match="External"):
        primary_model_path(container)


def test_all_package_relationships_reject_external_targets():
    output = BytesIO()
    relationships = b'''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="https://evil.example/settings" TargetMode="External" Id="r1" Type="https://schemas.example/cura"/></Relationships>'''
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("3D/_rels/3dmodel.model.rels", relationships)
    with pytest.raises(UnsafeThreeMFError, match="External package"):
        validate_relationships(ThreeMFContainer.from_bytes(output.getvalue()))
