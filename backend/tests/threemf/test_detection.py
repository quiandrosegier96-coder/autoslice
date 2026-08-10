from app.threemf.container.reader import ThreeMFContainer
from app.threemf.detection.detector import detect_3mf
from app.threemf.domain.metadata import SlicerType


def test_detection_uses_metadata_evidence(core_3mf_bytes):
    result = detect_3mf(ThreeMFContainer.from_bytes(core_3mf_bytes))
    assert result.slicer is SlicerType.BAMBU
    assert result.confidence >= 0.5


def test_anycubic_specific_file_outweighs_shared_keys(three_mf_factory):
    payload = three_mf_factory({"Metadata/AnycubicSlicer.config": b"{}", "Metadata/project_settings.config": b'{"filament_colour": [], "filament_type": [], "printer_settings_id": "x"}'})
    assert detect_3mf(ThreeMFContainer.from_bytes(payload)).slicer is SlicerType.ANYCUBIC


def test_core_only_package_is_not_claimed_by_a_slicer(three_mf_factory):
    model = b'<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><resources/><build/></model>'
    result = detect_3mf(ThreeMFContainer.from_bytes(three_mf_factory(model_xml=model)))
    assert result.slicer is SlicerType.CORE
    assert result.evidence


def test_package_without_primary_model_is_unknown():
    container = ThreeMFContainer({"[Content_Types].xml": b"<Types/>"})
    result = detect_3mf(container)
    assert result.slicer is SlicerType.UNKNOWN
    assert result.confidence == 0
    assert result.evidence
