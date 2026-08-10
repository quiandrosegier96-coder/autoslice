from pathlib import Path

import pytest

from app.threemf.conversion import convert_3mf
from app.threemf.domain.settings import ConversionContext
from app.threemf.validation import validate_3mf

FIXTURES = Path(__file__).parents[1] / "fixtures" / "3mf"


@pytest.mark.parametrize("source_folder", ["bambu", "anycubic"])
def test_real_source_to_anycubic_pipeline(source_folder):
    candidates = sorted((FIXTURES / source_folder).glob("*.3mf"))
    if not candidates:
        pytest.skip(f"No real {source_folder} fixture available for the complete conversion pipeline.")
    result = convert_3mf(
        candidates[0],
        ConversionContext("anycubic", target_printer_id="kobra_s1", nozzle_size_mm=0.4, material_id="pla"),
    )
    assert result.output_filename.endswith("_AutoSlice.3mf")
    assert validate_3mf(result.output).valid
    assert result.report.compatibility_score >= 0
