"""Conversion output and phase performance measurements."""

from dataclasses import dataclass

from app.threemf.domain.diagnostics import TranslationReport
from app.threemf.domain.metadata import SourceInfo


@dataclass(frozen=True)
class ConversionTimings:
    input_ms: float = 0.0
    detection_parse_ms: float = 0.0
    translation_ms: float = 0.0
    export_ms: float = 0.0
    validation_ms: float = 0.0
    total_ms: float = 0.0


@dataclass(frozen=True)
class ConversionResult:
    conversion_id: str
    output: bytes
    output_filename: str
    source: SourceInfo
    target_slicer: str
    target_printer_id: str | None
    report: TranslationReport
    timings: ConversionTimings
    input_size_bytes: int
    output_size_bytes: int
