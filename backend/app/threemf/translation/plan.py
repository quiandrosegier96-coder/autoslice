"""Capability-derived, source/target-neutral translation planning."""

from dataclasses import dataclass

from app.threemf.capabilities import FeatureSupport, capabilities_for, target_capabilities_for
from app.threemf.domain.diagnostics import Severity, TranslationItem, TranslationReport, TranslationStatus
from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.metadata import SlicerType


@dataclass(frozen=True)
class TranslationPlan:
    source: SlicerType
    target: SlicerType
    operations: tuple[TranslationItem, ...]

    @property
    def report(self) -> TranslationReport:
        return TranslationReport(self.operations).with_weighted_score()


def build_translation_plan(document: Universal3MFDocument, target: SlicerType) -> TranslationPlan:
    source_profile = capabilities_for(document.source.slicer)
    target_profile = target_capabilities_for(target)
    features = sorted({item.feature for item in source_profile.capabilities} | {item.feature for item in target_profile.capabilities})
    operations: list[TranslationItem] = []
    for feature in features:
        source = source_profile.for_feature(feature).support
        destination = target_profile.for_feature(feature).support
        status = _status(source, destination)
        severity = Severity.INFO if status in {TranslationStatus.SUPPORTED, TranslationStatus.PRESERVED} else Severity.MEDIUM
        if status is TranslationStatus.UNSUPPORTED:
            severity = Severity.HIGH
        operations.append(TranslationItem(
            feature, status, severity, source_value=source.value, target_value=destination.value,
            reason=f"Capability comparison: source={source.value}, target={destination.value}.",
        ))
    return TranslationPlan(document.source.slicer, target, tuple(operations))


def _status(source: FeatureSupport, target: FeatureSupport) -> TranslationStatus:
    if source is FeatureSupport.UNSUPPORTED:
        return TranslationStatus.PRESERVED
    return {
        FeatureSupport.SUPPORTED: TranslationStatus.SUPPORTED,
        FeatureSupport.SUPPORTED_WITH_LIMITS: TranslationStatus.SUPPORTED_WITH_LIMITS,
        FeatureSupport.APPROXIMATED: TranslationStatus.APPROXIMATED,
        FeatureSupport.PRESERVED_OPAQUE: TranslationStatus.PRESERVED_OPAQUE,
        FeatureSupport.UNSUPPORTED: TranslationStatus.UNSUPPORTED,
    }[target]
