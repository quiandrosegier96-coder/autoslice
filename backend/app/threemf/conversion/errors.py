"""Stable conversion failure categories for API and observability layers."""

from enum import Enum


class ConversionErrorCode(str, Enum):
    INVALID_3MF = "INVALID_3MF"
    UNSUPPORTED_SLICER = "UNSUPPORTED_SLICER"
    LOW_DETECTION_CONFIDENCE = "LOW_DETECTION_CONFIDENCE"
    PARSER_ERROR = "PARSER_ERROR"
    TRANSLATION_ERROR = "TRANSLATION_ERROR"
    EXPORT_ERROR = "EXPORT_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNSUPPORTED_FEATURE = "UNSUPPORTED_FEATURE"


class ConversionError(RuntimeError):
    def __init__(
        self, code: ConversionErrorCode, message: str, *, cause: Exception | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.cause = cause
