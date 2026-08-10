"""Target exporter contract; exporters never choose printer context themselves."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.threemf.domain.diagnostics import TranslationReport
from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.metadata import SlicerType
from app.threemf.domain.settings import ConversionContext


@dataclass(frozen=True)
class ExportResult:
    payload: bytes
    target: SlicerType
    report: TranslationReport


class ThreeMFExporter(ABC):
    @abstractmethod
    def can_export(self, target: SlicerType) -> bool:
        raise NotImplementedError

    @abstractmethod
    def export(self, document: Universal3MFDocument, context: ConversionContext) -> ExportResult:
        raise NotImplementedError
