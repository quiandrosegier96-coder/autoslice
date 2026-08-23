from app.models.print_settings import PrintSettings
from app.models.printer import FilamentType, PrinterProfile
from app.threemf.container.reader import ThreeMFContainer
from app.threemf.domain.metadata import SlicerType
from app.threemf.domain.settings import ConversionContext
from app.threemf.exporters.anycubic_native import NativeAnycubicExporter
from app.threemf.parsers.anycubic import AnycubicParser
from app.threemf.parsers.bambu import BambuParser
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


def test_native_anycubic_export_preserves_objects_components_and_build(three_mf_factory):
    source = three_mf_factory({"Metadata/BambuStudio.config": b"{}"})
    document = BambuParser().parse(ThreeMFContainer.from_bytes(source, "source.3mf"))
    exporter = NativeAnycubicExporter(_settings(), _printer(), FilamentType.PLA)
    result = exporter.export(document, ConversionContext("anycubic", target_printer_id="test_printer"))
    assert validate_3mf(result.payload).valid
    reparsed = AnycubicParser().parse(ThreeMFContainer.from_bytes(result.payload))
    assert reparsed.source.slicer is SlicerType.ANYCUBIC
    assert len(reparsed.objects) == len(document.objects)
    assert reparsed.objects[1].components[0].object_id == reparsed.objects[0].object_id
    assert reparsed.build.items[0].transform.values == document.build.items[0].transform.values


def test_native_anycubic_export_never_creates_round_robin_mapping(three_mf_factory):
    source = three_mf_factory({"Metadata/BambuStudio.config": b"{}"})
    document = BambuParser().parse(ThreeMFContainer.from_bytes(source))
    result = NativeAnycubicExporter(_settings(), _printer(), FilamentType.PLA).export(
        document, ConversionContext("anycubic", target_printer_id="test_printer"),
    )
    container = ThreeMFContainer.from_bytes(result.payload)
    assert not container.exists("Metadata/model_settings.config")


def test_registered_anycubic_exporter_resolves_target_from_context(three_mf_factory):
    source = three_mf_factory({"Metadata/BambuStudio.config": b"{}"})
    document = BambuParser().parse(ThreeMFContainer.from_bytes(source))
    result = NativeAnycubicExporter().export(
        document, ConversionContext("anycubic", target_printer_id="kobra_s1", material_id="pla"),
    )
    assert validate_3mf(result.payload).valid
    assert AnycubicParser().parse(ThreeMFContainer.from_bytes(result.payload)).objects
