"""Anycubic Slicer adapter layered on the slicer-neutral core parser."""

from dataclasses import replace

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.detection.detector import DetectionResult, detect_3mf
from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.metadata import SlicerType
from app.threemf.parsers.base import ThreeMFParser
from app.threemf.parsers.core import CoreThreeMFParser
from app.threemf.parsers.slicer_config import enrich_prusaslicer_family


class AnycubicParser(ThreeMFParser):
    def __init__(self, core: CoreThreeMFParser | None = None) -> None:
        self._core = core or CoreThreeMFParser()

    def can_parse(self, container: ThreeMFContainer) -> DetectionResult:
        detected = detect_3mf(container)
        return detected if detected.slicer is SlicerType.ANYCUBIC else DetectionResult(SlicerType.ANYCUBIC, 0.0)

    def parse(self, container: ThreeMFContainer) -> Universal3MFDocument:
        detection = self.can_parse(container)
        if detection.confidence <= 0:
            raise ValueError("AnycubicParser cannot parse a package not detected as Anycubic Slicer.")
        document = enrich_prusaslicer_family(self._core.parse(container), container)
        return replace(document, source=replace(
            document.source, slicer=SlicerType.ANYCUBIC, confidence=detection.confidence,
            detection_evidence=detection.evidence, version=detection.version,
        ))
