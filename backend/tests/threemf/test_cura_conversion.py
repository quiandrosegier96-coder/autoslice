from pathlib import Path

import pytest

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.conversion import convert_3mf
from app.threemf.domain.settings import ConversionContext
from app.threemf.parsers.anycubic import AnycubicParser
from app.threemf.validation import validate_3mf

FIXTURE = Path(__file__).parents[1] / "fixtures" / "3mf" / "cura" / "cura_basic.3mf"


def test_real_cura_to_universal_to_anycubic():
    if not FIXTURE.exists():
        pytest.skip("SKIPPED — real cura_basic.3mf unavailable; Cura→Anycubic is not certified.")
    result = convert_3mf(FIXTURE, ConversionContext(
        "anycubic", target_printer_id="kobra_s1", nozzle_size_mm=0.4,
        material_id="pla", source_slicer="cura",
    ))
    assert result.output_filename == "cura_basic_AutoSlice.3mf"
    assert validate_3mf(result.output).valid
    assert AnycubicParser().parse(ThreeMFContainer.from_bytes(result.output)).objects
