"""Capability levels are richer than yes/no support."""

from dataclasses import dataclass
from enum import Enum

from app.threemf.domain.metadata import SlicerType


class FeatureSupport(str, Enum):
    UNSUPPORTED = "unsupported"
    SUPPORTED = "supported"
    SUPPORTED_WITH_LIMITS = "supported_with_limits"
    APPROXIMATED = "approximated"
    PRESERVED_OPAQUE = "preserved_opaque"


@dataclass(frozen=True)
class Capability:
    feature: str
    support: FeatureSupport
    limits: tuple[tuple[str, str], ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class SlicerCapabilities:
    slicer: SlicerType
    capabilities: tuple[Capability, ...] = ()

    def for_feature(self, feature: str) -> Capability:
        return next((item for item in self.capabilities if item.feature == feature), Capability(feature, FeatureSupport.UNSUPPORTED))
