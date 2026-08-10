from pathlib import Path

import pytest

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.domain.metadata import SlicerType
from app.threemf.parsers.orca import OrcaParser

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "3mf" / "orca"


def _real_orca(name: str) -> Path:
    path = FIXTURE_DIR / name
    if not path.exists():
        pytest.skip(f"SKIPPED — real Orca fixture unavailable: {path.name}; see fixtures/3mf/orca/README.md")
    return path


def test_orca_basic_real_fixture_detection_parse_and_preservation():
    container = ThreeMFContainer.from_path(_real_orca("orca_basic.3mf"))
    parser = OrcaParser()
    detection = parser.can_parse(container)
    assert detection.slicer is SlicerType.ORCA
    assert detection.confidence >= 0.5
    assert detection.evidence
    document = parser.parse(container)
    assert document.objects
    assert document.build.items
    assert document.process.layer_height_mm is not None
    assert document.resources.opaque


def test_orca_multi_object_real_fixture_identity_components_transforms():
    document = OrcaParser().parse(ThreeMFContainer.from_path(_real_orca("orca_multi_object.3mf")))
    assert len(document.objects) > 1
    assert len({obj.object_id for obj in document.objects}) == len(document.objects)
    assert any(obj.components for obj in document.objects)
    assert document.build.items


def test_orca_multi_plate_real_fixture():
    document = OrcaParser().parse(ThreeMFContainer.from_path(_real_orca("orca_multi_plate.3mf")))
    assert len(document.build.plates) >= 2


def test_orca_multicolor_real_fixture_material_mapping():
    document = OrcaParser().parse(ThreeMFContainer.from_path(_real_orca("orca_multicolor.3mf")))
    assert len(document.tool_assignments) > 1
    assert any(obj.material_resource_id for obj in document.objects)


def test_orca_modifier_real_fixture():
    document = OrcaParser().parse(ThreeMFContainer.from_path(_real_orca("orca_modifier.3mf")))
    assert any(obj.role.value in {"modifier", "negative_volume"} for obj in document.objects)


def test_orca_support_real_fixture_preserves_source_payload():
    document = OrcaParser().parse(ThreeMFContainer.from_path(_real_orca("orca_supports.3mf")))
    assert document.resources.opaque or document.supports.regions
