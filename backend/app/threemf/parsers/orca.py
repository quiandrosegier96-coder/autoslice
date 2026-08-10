"""Fixture-gated OrcaSlicer adapter over core and shared project semantics."""

from dataclasses import replace

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.detection.detector import DetectionResult, detect_3mf
from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.metadata import SlicerType
from app.threemf.parsers.base import ThreeMFParser
from app.threemf.parsers.core import CoreThreeMFParser
from app.threemf.parsers.slicer_config import enrich_prusaslicer_family


class OrcaParser(ThreeMFParser):
    """Parse only proven core/shared semantics; Orca-specific parts remain opaque."""

    def __init__(self, core: CoreThreeMFParser | None = None) -> None:
        self._core = core or CoreThreeMFParser()

    def can_parse(self, container: ThreeMFContainer) -> DetectionResult:
        detected = detect_3mf(container)
        return detected if detected.slicer is SlicerType.ORCA else DetectionResult(SlicerType.ORCA, 0.0)

    def parse(self, container: ThreeMFContainer) -> Universal3MFDocument:
        detection = self.can_parse(container)
        if detection.confidence <= 0:
            raise ValueError("OrcaParser requires explicit OrcaSlicer detection evidence.")
        document = enrich_prusaslicer_family(self._core.parse(container), container)
        return replace(document, source=replace(
            document.source, slicer=SlicerType.ORCA, confidence=detection.confidence,
            detection_evidence=detection.evidence, version=detection.version,
        ))
