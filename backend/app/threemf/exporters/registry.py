from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.metadata import SlicerType
from app.threemf.domain.settings import ConversionContext
from app.threemf.exporters.base import ExportResult, ThreeMFExporter


class ExporterRegistry:
    def __init__(self, exporters: tuple[ThreeMFExporter, ...] = ()) -> None:
        self._exporters = list(exporters)

    def register(self, exporter: ThreeMFExporter) -> None:
        self._exporters.append(exporter)

    def get_exporter(self, target: SlicerType) -> ThreeMFExporter:
        exporter = next((item for item in self._exporters if item.can_export(target)), None)
        if exporter is None:
            raise ValueError(f"No exporter registered for target '{target.value}'.")
        return exporter

    def export(self, target: SlicerType, document: Universal3MFDocument, context: ConversionContext) -> ExportResult:
        return self.get_exporter(target).export(document, context)


def default_exporter_registry() -> ExporterRegistry:
    from app.threemf.exporters.anycubic_native import NativeAnycubicExporter

    return ExporterRegistry((NativeAnycubicExporter(),))
