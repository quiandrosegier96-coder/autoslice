"""Structured diagnostics and compatibility reporting primitives."""

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TranslationStatus(str, Enum):
    SUPPORTED = "supported"
    SUPPORTED_WITH_LIMITS = "supported_with_limits"
    APPROXIMATED = "approximated"
    UNSUPPORTED = "unsupported"
    PRESERVED = "preserved"
    PRESERVED_OPAQUE = "preserved_opaque"


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    severity: Severity = Severity.INFO
    path: str | None = None


@dataclass(frozen=True)
class TranslationItem:
    feature: str
    status: TranslationStatus
    severity: Severity
    source_value: str | None = None
    universal_value: str | None = None
    target_value: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class TranslationReport:
    items: tuple[TranslationItem, ...] = ()
    compatibility_score: float = 100.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.compatibility_score <= 100.0:
            raise ValueError("Compatibility score must be between 0 and 100.")

    def with_weighted_score(self, weights: dict[Severity, float] | None = None) -> "TranslationReport":
        configured = weights or {
            Severity.INFO: 0.0, Severity.LOW: 2.0, Severity.MEDIUM: 8.0,
            Severity.HIGH: 20.0, Severity.CRITICAL: 40.0,
        }
        penalties = {
            TranslationStatus.SUPPORTED: 0.0, TranslationStatus.PRESERVED: 0.0,
            TranslationStatus.SUPPORTED_WITH_LIMITS: 0.25,
            TranslationStatus.PRESERVED_OPAQUE: 0.15,
            TranslationStatus.APPROXIMATED: 0.6, TranslationStatus.UNSUPPORTED: 1.0,
        }
        loss = sum(configured[item.severity] * penalties[item.status] for item in self.items)
        return TranslationReport(self.items, max(0.0, round(100.0 - loss, 2)))
