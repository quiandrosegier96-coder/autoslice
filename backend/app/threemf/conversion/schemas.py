"""Pydantic report schemas suitable for a future API response."""

from pydantic import BaseModel, Field

from app.threemf.conversion.result import ConversionResult


class SourceSchema(BaseModel):
    slicer: str
    confidence: float
    evidence: list[str]


class TargetSchema(BaseModel):
    slicer: str
    printer: str | None = None


class TranslationItemSchema(BaseModel):
    feature: str
    status: str
    severity: str
    source_value: str | None = None
    universal_value: str | None = None
    target_value: str | None = None
    reason: str


class TimingSchema(BaseModel):
    input_ms: float
    detection_parse_ms: float
    translation_ms: float
    export_ms: float
    validation_ms: float
    total_ms: float


class ConversionReportSchema(BaseModel):
    conversion_id: str
    source: SourceSchema
    target: TargetSchema
    compatibility_score: float = Field(ge=0, le=100)
    translated: list[TranslationItemSchema]
    modified: list[TranslationItemSchema]
    approximated: list[TranslationItemSchema]
    unsupported: list[TranslationItemSchema]
    preserved: list[TranslationItemSchema]
    warnings: list[str]
    output_filename: str
    timings: TimingSchema

    @classmethod
    def from_result(cls, result: ConversionResult) -> "ConversionReportSchema":
        values = [TranslationItemSchema(
            feature=item.feature, status=item.status.value, severity=item.severity.value,
            source_value=item.source_value, universal_value=item.universal_value,
            target_value=item.target_value, reason=item.reason,
        ) for item in result.report.items]
        by_status = lambda *statuses: [item for item in values if item.status in statuses]
        return cls(
            conversion_id=result.conversion_id,
            source=SourceSchema(slicer=result.source.slicer.value, confidence=result.source.confidence, evidence=list(result.source.detection_evidence)),
            target=TargetSchema(slicer=result.target_slicer, printer=result.target_printer_id),
            compatibility_score=result.report.compatibility_score,
            translated=by_status("supported", "supported_with_limits"),
            modified=by_status("approximated"), approximated=by_status("approximated"),
            unsupported=by_status("unsupported"), preserved=by_status("preserved", "preserved_opaque"),
            warnings=[item.reason for item in values if item.severity in {"medium", "high", "critical"}],
            output_filename=result.output_filename, timings=TimingSchema(**result.timings.__dict__),
        )
