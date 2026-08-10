from pathlib import Path

import pytest

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.domain.metadata import SlicerType
from app.threemf.parsers.prusa import PrusaParser

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "3mf" / "prusa"


def _fixture(name: str) -> Path:
    path = FIXTURE_DIR / name
    if not path.exists():
        pytest.skip(f"SKIPPED — real PrusaSlicer fixture unavailable: {name}")
    return path


def test_prusa_basic_real_detection_and_parse():
    container = ThreeMFContainer.from_path(_fixture("prusa_basic.3mf"))
    detection = PrusaParser().can_parse(container)
    assert detection.slicer is SlicerType.PRUSA and detection.evidence
    document = PrusaParser().parse(container)
    assert document.objects and document.build.items


@pytest.mark.parametrize("name", ["prusa_multi_object.3mf", "prusa_multimaterial.3mf", "prusa_multi_plate.3mf", "prusa_modifier.3mf", "prusa_supports.3mf"])
def test_prusa_feature_fixtures_preserve_data(name):
    document = PrusaParser().parse(ThreeMFContainer.from_path(_fixture(name)))
    assert document.objects
    assert document.resources.opaque or document.materials or document.supports.regions
