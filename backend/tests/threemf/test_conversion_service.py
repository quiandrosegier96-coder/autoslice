import pytest

from app.threemf.conversion.errors import ConversionError, ConversionErrorCode
from app.threemf.conversion.service import ConversionService
from app.threemf.conversion.schemas import ConversionReportSchema
from app.threemf.domain.diagnostics import TranslationReport
from app.threemf.domain.metadata import SlicerType
from app.threemf.domain.settings import ConversionContext
from app.threemf.exporters.base import ExportResult
from app.threemf.exporters.base import ThreeMFExporter
from app.threemf.exporters.registry import ExporterRegistry
from app.threemf.parsers import default_parser_registry
from app.threemf.translation.engine import TargetArtifacts, TranslationOutcome


class PassthroughTranslator:
    def translate(self, document, context):
        return TranslationOutcome(document, TranslationReport(), TargetArtifacts(None, None, None))


class StaticExporter(ThreeMFExporter):
    def __init__(self, payload):
        self.payload = payload

    def can_export(self, target):
        return target is SlicerType.ANYCUBIC

    def export(self, document, context):
        return ExportResult(self.payload, SlicerType.ANYCUBIC, TranslationReport())


def test_conversion_service_runs_secure_parse_export_validate_reparse(three_mf_factory):
    target_payload = three_mf_factory({"Metadata/AnycubicSlicer.config": b"{}"})
    service = ConversionService(
        default_parser_registry(), PassthroughTranslator(),
        ExporterRegistry((StaticExporter(target_payload),)),
    )
    source = three_mf_factory({"Metadata/BambuStudio.config": b"{}"})
    result = service.convert_3mf(
        source, ConversionContext("anycubic", target_printer_id="kobra_s1", material_id="pla"),
        original_filename="dragon.3mf",
    )
    assert result.output_filename == "dragon_AutoSlice.3mf"
    assert result.source.slicer is SlicerType.BAMBU
    assert result.output == target_payload
    assert result.timings.total_ms >= 0
    schema = ConversionReportSchema.from_result(result)
    assert schema.source.slicer == "bambu"
    assert schema.target.slicer == "anycubic"
    assert schema.output_filename == "dragon_AutoSlice.3mf"


def test_conversion_service_rejects_invalid_export(three_mf_factory):
    service = ConversionService(
        default_parser_registry(), PassthroughTranslator(),
        ExporterRegistry((StaticExporter(b"not-a-zip"),)),
    )
    source = three_mf_factory({"Metadata/BambuStudio.config": b"{}"})
    with pytest.raises(ConversionError) as caught:
        service.convert_3mf(source, ConversionContext("anycubic", target_printer_id="kobra_s1"))
    assert caught.value.code is ConversionErrorCode.VALIDATION_ERROR
