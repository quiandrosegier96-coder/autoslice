from pathlib import Path

import pytest

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.domain.metadata import SlicerType
from app.threemf.parsers.cura import CuraParser

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "3mf" / "cura"


def _fixture(name: str) -> Path:
    path = FIXTURE_DIR / name
    if not path.exists():
        pytest.skip(f"SKIPPED — real Cura fixture unavailable: {name}")
    return path


def test_cura_basic_real_fixture_to_universal():
    container = ThreeMFContainer.from_path(_fixture("cura_basic.3mf"))
    detection = CuraParser().can_parse(container)
    assert detection.slicer is SlicerType.CURA and detection.evidence
    document = CuraParser().parse(container)
    assert document.objects and document.build.items


@pytest.mark.parametrize("name", ["cura_multi_object.3mf", "cura_multimaterial.3mf", "cura_multi_part.3mf", "cura_modifier.3mf", "cura_supports.3mf", "cura_multi_build.3mf"])
def test_cura_feature_fixture_preserves_semantics_or_opaque(name):
    document = CuraParser().parse(ThreeMFContainer.from_path(_fixture(name)))
    assert document.objects
    assert document.resources.opaque or document.materials or document.supports.regions
