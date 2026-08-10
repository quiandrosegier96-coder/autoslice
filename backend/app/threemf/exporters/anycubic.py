"""Temporary Universal3MF adapter around the existing Anycubic exporter."""

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import zipfile

from app.export.anycubic_exporter import export as legacy_export
from app.ingestion.unpacker import UnpackedArchive
from app.models.print_settings import PrintSettings as LegacyPrintSettings
from app.models.printer import FilamentType, PrinterProfile
from app.parser.model_parser import ParsedModel, RawMeshObject
from app.threemf.domain.diagnostics import Severity, TranslationItem, TranslationReport, TranslationStatus
from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.metadata import SlicerType
from app.threemf.domain.settings import ConversionContext
from app.threemf.exporters.base import ExportResult, ThreeMFExporter
from app.threemf.validation import validate_3mf


class AnycubicExporterAdapter(ThreeMFExporter):
    """Bridge only: mesh flattening remains an explicitly reported legacy target limitation."""

    def __init__(self, settings: LegacyPrintSettings, printer: PrinterProfile, filament: FilamentType) -> None:
        self._settings = settings
        self._printer = printer
        self._filament = filament

    def can_export(self, target: SlicerType) -> bool:
        return target is SlicerType.ANYCUBIC

    def export(self, document: Universal3MFDocument, context: ConversionContext) -> ExportResult:
        if context.target_slicer != SlicerType.ANYCUBIC.value:
            raise ValueError("AnycubicExporterAdapter requires an Anycubic conversion context.")
        parsed = _legacy_model(document)
        report = _legacy_report(document)
        with TemporaryDirectory(prefix="autoslice-anycubic-") as temporary:
            root = Path(temporary)
            extract_dir = root / "source"
            extract_dir.mkdir()
            all_files = _write_preserved_assets(document, extract_dir)
            archive = UnpackedArchive(extract_dir, None, [], None, all_files=all_files)
            output_path = root / "output.3mf"
            legacy_export(
                archive, self._settings, self._printer, self._filament, output_path,
                parsed_model=parsed, scale_factor=1.0,
            )
            with zipfile.ZipFile(output_path, "a", compression=zipfile.ZIP_DEFLATED) as package:
                package.writestr("Metadata/AnycubicSlicer.config", json.dumps({
                    "generator": "AutoSlice", "target": "Anycubic Slicer",
                    "adapter": "legacy-anycubic-v1",
                    "original_project_name": document.preservation.original_project_name,
                }, indent=2))
            payload = output_path.read_bytes()
        validate_3mf(payload).require_valid()
        return ExportResult(payload, SlicerType.ANYCUBIC, report.with_weighted_score())


def _legacy_model(document: Universal3MFDocument) -> ParsedModel:
    objects = []
    for obj in document.objects:
        if obj.mesh is None:
            continue
        objects.append(RawMeshObject(
            obj.object_id, obj.name,
            list(obj.mesh.vertices), [triangle.vertices for triangle in obj.mesh.triangles],
            obj.role.value,
        ))
    return ParsedModel(objects=objects, unit="millimeter")


def _write_preserved_assets(document: Universal3MFDocument, extract_dir: Path) -> list[Path]:
    written: list[Path] = []
    payloads = [(item.path, item.payload) for item in document.resources.opaque]
    payloads.extend((texture.path, texture.payload) for texture in document.resources.textures if texture.payload is not None)
    for relative, payload in payloads:
        if not relative or payload is None or relative in {"[Content_Types].xml", "_rels/.rels", document.package.primary_model_path}:
            continue
        target = extract_dir.joinpath(*Path(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        written.append(target)
    return written


def _legacy_report(document: Universal3MFDocument) -> TranslationReport:
    items = [TranslationItem(
        "geometry", TranslationStatus.SUPPORTED_WITH_LIMITS, Severity.HIGH,
        universal_value=f"{len(document.objects)} objects", target_value="one merged mesh",
        reason="LEGACY TARGET LIMITATION: the existing Anycubic exporter flattens printable meshes.",
    )]
    if any(obj.components for obj in document.objects):
        items.append(TranslationItem(
            "component_instancing", TranslationStatus.UNSUPPORTED, Severity.HIGH,
            reason="The legacy exporter does not preserve component instances or build transforms.",
        ))
    if document.tool_assignments or any(obj.material_resource_id for obj in document.objects):
        items.append(TranslationItem(
            "material_mapping", TranslationStatus.APPROXIMATED, Severity.HIGH,
            reason="The legacy multicolor exporter uses round-robin assignment; Universal3MF itself does not.",
        ))
    items.append(TranslationItem(
        "opaque_source_data", TranslationStatus.PRESERVED_OPAQUE, Severity.LOW,
        reason="Safe source assets are offered to the legacy exporter; target-specific configs may still be replaced.",
    ))
    return TranslationReport(tuple(items))
