from pathlib import Path

import pytest

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.conversion import convert_3mf
from app.threemf.domain.settings import ConversionContext, ConversionMode
from app.threemf.parsers.anycubic import AnycubicParser

FIXTURE = Path(__file__).parents[1] / "fixtures" / "3mf" / "prusa" / "prusa_basic.3mf"


def test_prusa_to_anycubic_real_fixture_validation_gate():
    if not FIXTURE.exists():
        pytest.skip("SKIPPED — real prusa_basic.3mf unavailable; Prusa→Anycubic is not certified.")
    context = ConversionContext(
        target_slicer="anycubic", target_printer_id="kobra_s1_combo",
        material_id="pla", nozzle_size_mm=0.4, mode=ConversionMode.AUTOSLICE,
    )
    result = convert_3mf(FIXTURE, context)
    assert result.output_filename.endswith("_AutoSlice.3mf")
    assert result.output
    reparsed = AnycubicParser().parse(ThreeMFContainer.from_bytes(result.output))
    assert reparsed.objects and reparsed.build.items
