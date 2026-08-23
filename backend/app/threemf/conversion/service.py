"""Central secure Universal3MF conversion orchestration service."""

import logging
from pathlib import Path
from time import perf_counter
import uuid

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.conversion.errors import ConversionError, ConversionErrorCode
from app.threemf.conversion.result import ConversionResult, ConversionTimings
from app.threemf.detection import detect_3mf
from app.threemf.domain.diagnostics import TranslationReport
from app.threemf.domain.metadata import SlicerType
from app.threemf.domain.settings import ConversionContext
from app.threemf.exporters.registry import ExporterRegistry, default_exporter_registry
from app.threemf.pipeline.naming import autoslice_output_filename
from app.threemf.parsers.registry import ParserRegistry, default_parser_registry
from app.threemf.translation.engine import AutoSliceTranslationEngine
from app.threemf.validation import TargetValidatorRegistry, default_target_validator_registry

logger = logging.getLogger(__name__)
class ConversionService:
    def __init__(
        self,
        parser_registry: ParserRegistry,
        translator: AutoSliceTranslationEngine,
        exporter_registry: ExporterRegistry,
        target_validators: TargetValidatorRegistry | None = None,
        min_detection_confidence: float = 0.5,
    ) -> None:
        self._parsers = parser_registry
        self._translator = translator
        self._exporters = exporter_registry
        self._target_validators = target_validators or default_target_validator_registry()
        self._min_detection_confidence = min_detection_confidence

    def convert_3mf(
        self,
        value: bytes | Path,
        context: ConversionContext,
        *,
        original_filename: str | None = None,
        existing_filenames: set[str] | None = None,
    ) -> ConversionResult:
        conversion_id = str(uuid.uuid4())
        started = perf_counter()
        logger.info("3MF conversion started", extra={"conversion_id": conversion_id})
        raw = value.read_bytes() if isinstance(value, Path) else value
        filename = original_filename or (value.name if isinstance(value, Path) else "project.3mf")
        input_done = perf_counter()
        try:
            container = ThreeMFContainer.from_bytes(raw, filename)
        except ValueError as exc:
            raise ConversionError(ConversionErrorCode.INVALID_3MF, str(exc), cause=exc) from exc
        detection = detect_3mf(container)
        if detection.slicer is SlicerType.UNKNOWN:
            raise ConversionError(ConversionErrorCode.UNSUPPORTED_SLICER, "The source 3MF format could not be identified.")
        if detection.confidence < self._min_detection_confidence:
            raise ConversionError(
                ConversionErrorCode.LOW_DETECTION_CONFIDENCE,
                f"Source detection confidence {detection.confidence:.2f} is below the required threshold {self._min_detection_confidence:.2f}.",
            )
        if context.source_slicer and context.source_slicer != detection.slicer.value:
            raise ConversionError(
                ConversionErrorCode.UNSUPPORTED_SLICER,
                f"Detected source '{detection.slicer.value}' does not match requested source '{context.source_slicer}'.",
            )
        logger.info("3MF source detected", extra={"conversion_id": conversion_id, "source_slicer": detection.slicer.value, "confidence": detection.confidence})
        try:
            document = self._parsers.parse(container)
        except Exception as exc:
            raise ConversionError(ConversionErrorCode.PARSER_ERROR, f"Failed to parse source 3MF: {exc}", cause=exc) from exc
        parse_done = perf_counter()
        logger.info("3MF parsed", extra={"conversion_id": conversion_id, "object_count": len(document.objects)})
        try:
            target = SlicerType(context.target_slicer)
            self._exporters.get_exporter(target)
        except ValueError as exc:
            raise ConversionError(ConversionErrorCode.UNSUPPORTED_SLICER, f"Unsupported target slicer: {context.target_slicer}", cause=exc) from exc
        try:
            outcome = self._translator.translate(document, context)
        except Exception as exc:
            raise ConversionError(ConversionErrorCode.TRANSLATION_ERROR, f"AutoSlice translation failed: {exc}", cause=exc) from exc
        translation_done = perf_counter()
        logger.info("3MF translated and optimized", extra={"conversion_id": conversion_id, "compatibility": outcome.report.compatibility_score})
        try:
            exported = self._exporters.export(target, outcome.document, context)
        except ConversionError:
            raise
        except Exception as exc:
            raise ConversionError(ConversionErrorCode.EXPORT_ERROR, f"Target export failed: {exc}", cause=exc) from exc
        export_done = perf_counter()
        logger.info("3MF exported", extra={"conversion_id": conversion_id, "output_size": len(exported.payload)})
        try:
            validation = self._target_validators.validate(target, exported.payload)
        except Exception as exc:
            raise ConversionError(ConversionErrorCode.VALIDATION_ERROR, f"Target validation failed: {exc}", cause=exc) from exc
        if not validation.valid:
            detail = "; ".join(item.message for item in validation.diagnostics)
            raise ConversionError(ConversionErrorCode.VALIDATION_ERROR, f"Generated 3MF failed validation: {detail}")
        try:
            reparsed = self._parsers.parse(ThreeMFContainer.from_bytes(exported.payload, "output.3mf"))
            if reparsed.source.slicer.value != context.target_slicer:
                raise ValueError(
                    f"Generated package identifies as {reparsed.source.slicer.value}, expected {context.target_slicer}."
                )
        except Exception as exc:
            raise ConversionError(ConversionErrorCode.VALIDATION_ERROR, f"Generated 3MF could not be reparsed: {exc}", cause=exc) from exc
        validation_done = perf_counter()
        logger.info("3MF validation completed", extra={"conversion_id": conversion_id})
        items = outcome.report.items + exported.report.items
        report = TranslationReport(items).with_weighted_score()
        output_filename = autoslice_output_filename(filename, existing_filenames)
        timings = ConversionTimings(
            input_ms=(input_done - started) * 1000,
            detection_parse_ms=(parse_done - input_done) * 1000,
            translation_ms=(translation_done - parse_done) * 1000,
            export_ms=(export_done - translation_done) * 1000,
            validation_ms=(validation_done - export_done) * 1000,
            total_ms=(validation_done - started) * 1000,
        )
        logger.info("3MF conversion completed", extra={"conversion_id": conversion_id, "output_filename": output_filename, "compatibility": report.compatibility_score})
        return ConversionResult(
            conversion_id, exported.payload, output_filename, document.source,
            context.target_slicer, context.target_printer_id, report, timings,
            len(raw), len(exported.payload),
        )


def create_conversion_service(min_detection_confidence: float = 0.5) -> ConversionService:
    return ConversionService(
        default_parser_registry(), AutoSliceTranslationEngine(), default_exporter_registry(),
        min_detection_confidence=min_detection_confidence,
    )


def create_anycubic_conversion_service(min_detection_confidence: float = 0.5) -> ConversionService:
    """Backward-compatible name for the now target-neutral production service."""
    return create_conversion_service(min_detection_confidence)


def convert_3mf(
    value: bytes | Path,
    context: ConversionContext,
    *,
    min_detection_confidence: float = 0.5,
    **kwargs,
) -> ConversionResult:
    """Default production-neutral entrypoint; no legacy fallback is automatic."""
    return create_conversion_service(min_detection_confidence).convert_3mf(value, context, **kwargs)
