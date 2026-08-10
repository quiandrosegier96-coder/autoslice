from pathlib import Path

import pytest

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.domain.metadata import SlicerType
from app.threemf.parsers.anycubic import AnycubicParser
from app.threemf.parsers.bambu import BambuParser

FIXTURES = Path(__file__).parents[1] / "fixtures" / "3mf"


def _fixture(folder: str) -> Path:
    candidates = sorted((FIXTURES / folder).glob("*.3mf"))
    if not candidates:
        pytest.skip(f"No real {folder} 3MF fixture is available; see fixtures/3mf/{folder}/README.md")
    return candidates[0]


def test_bambu_detection_and_parse_real_fixture():
    container = ThreeMFContainer.from_path(_fixture("bambu"))
    parser = BambuParser()
    detection = parser.can_parse(container)
    assert detection.slicer is SlicerType.BAMBU
    assert detection.confidence >= 0.5
    assert detection.evidence
    document = parser.parse(container)
    assert document.objects
    assert document.build.items


def test_anycubic_detection_and_parse_real_fixture():
    container = ThreeMFContainer.from_path(_fixture("anycubic"))
    parser = AnycubicParser()
    detection = parser.can_parse(container)
    assert detection.slicer is SlicerType.ANYCUBIC
    assert detection.confidence >= 0.5
    assert detection.evidence
    document = parser.parse(container)
    assert document.objects
    assert document.build.items
