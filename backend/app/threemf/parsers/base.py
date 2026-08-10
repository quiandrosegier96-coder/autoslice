"""Common parser contract for core and slicer-specific adapters."""

from abc import ABC, abstractmethod

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.detection.detector import DetectionResult
from app.threemf.domain.document import Universal3MFDocument


class ThreeMFParser(ABC):
    @abstractmethod
    def can_parse(self, container: ThreeMFContainer) -> DetectionResult:
        raise NotImplementedError

    @abstractmethod
    def parse(self, container: ThreeMFContainer) -> Universal3MFDocument:
        raise NotImplementedError
