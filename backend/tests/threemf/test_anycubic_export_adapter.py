from app.models.print_settings import PrintSettings
from app.models.printer import FilamentType, PrinterProfile
from app.threemf.comparison import inspect_package
from app.threemf.container.reader import ThreeMFContainer
from app.threemf.domain.diagnostics import TranslationStatus
from app.threemf.domain.metadata import SlicerType
from app.threemf.domain.settings import ConversionContext
from app.threemf.exporters.anycubic import AnycubicExporterAdapter
from app.threemf.parsers.bambu import BambuParser
from app.threemf.parsers.anycubic import AnycubicParser
from app.threemf.validation import validate_3mf


def _settings() -> PrintSettings:
    return PrintSettings(
        layer_height_mm=0.2, first_layer_height_mm=0.25, wall_count=3,
        top_layers=4, bottom_layers=4, infill_percent=15, infill_pattern="gyroid",
        supports_enabled=False, support_type="normal", support_density_percent=15,
        support_angle_threshold_deg=50, brim_enabled=False, brim_width_mm=5.0,
        skirt_loops=1, nozzle_temp_c=220, bed_temp_c=60,
        print_speed_mm_s=160, first_layer_speed_mm_s=30,
    )


def _printer() -> PrinterProfile:
    return PrinterProfile(
        id="test_printer", display_name="Test Printer", build_volume_x_mm=250,
        build_volume_y_mm=250, build_volume_z_mm=250, max_speed_mm_s=300,
        nozzle_diameter_mm=0.4, supported_filaments=[FilamentType.PLA],
    )


def test_universal_to_anycubic_legacy_adapter_is_self_consistent(three_mf_factory):
    source = three_mf_factory({"Metadata/BambuStudio.config": b"{}"})
    document = BambuParser().parse(ThreeMFContainer.from_bytes(source, "source.3mf"))
    adapter = AnycubicExporterAdapter(_settings(), _printer(), FilamentType.PLA)
    result = adapter.export(document, ConversionContext(SlicerType.ANYCUBIC.value, "test_printer", 0.4, "pla"))
    assert validate_3mf(result.payload).valid
    reparsed = AnycubicParser().parse(ThreeMFContainer.from_bytes(result.payload))
    assert reparsed.source.slicer is SlicerType.ANYCUBIC
    semantics = inspect_package(result.payload)
    assert semantics.mesh_count == 1
    assert semantics.build_item_count == 1
    assert any(item.status is TranslationStatus.SUPPORTED_WITH_LIMITS for item in result.report.items)
