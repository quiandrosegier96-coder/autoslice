"""AutoSlice optimization adapter around the existing analysis and rules engines."""

from dataclasses import dataclass, replace

from app.geometry.analyzer import analyze_mesh
from app.geometry.mesh_loader import merge_meshes
from app.models.printer import FilamentType, PrinterProfile
from app.models.print_settings import PrintSettings as LegacyPrintSettings
from app.normalization.intent import normalize
from app.parser.model_parser import ParsedModel, RawMeshObject
from app.rules.engine import generate_settings
from app.rules.printer_loader import load_printer_profile
from app.threemf.domain.diagnostics import Severity, TranslationItem, TranslationReport, TranslationStatus
from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.settings import ConversionContext, ConversionMode, PrintSettings


@dataclass(frozen=True)
class TargetArtifacts:
    settings: LegacyPrintSettings
    printer: PrinterProfile
    filament: FilamentType


@dataclass(frozen=True)
class TranslationOutcome:
    document: Universal3MFDocument
    report: TranslationReport
    target_artifacts: TargetArtifacts


class AutoSliceTranslationEngine:
    def translate(self, document: Universal3MFDocument, context: ConversionContext) -> TranslationOutcome:
        if context.mode is not ConversionMode.AUTOSLICE or context.preserve_source or not context.optimize_for_target:
            raise ValueError("Preserve mode export is not implemented until real roundtrip fixtures are available.")
        if not context.target_printer_id:
            raise ValueError("AutoSlice conversion requires a target printer profile.")
        try:
            filament = FilamentType(context.material_id or "pla")
        except ValueError as exc:
            raise ValueError(f"Unsupported target material: {context.material_id}") from exc
        printer = load_printer_profile(context.target_printer_id)
        nozzle = context.nozzle_size_mm or printer.nozzle_diameter_mm
        if filament not in printer.supported_filaments:
            raise ValueError(f"{filament.value.upper()} is not supported by {printer.display_name}.")
        parsed = _legacy_geometry(document)
        if not parsed.objects:
            raise ValueError("Universal3MF contains no directly exportable mesh objects.")
        mesh = merge_meshes(parsed.objects)
        geometry = analyze_mesh(mesh, len(parsed.objects))
        intent = normalize(geometry)
        printer.nozzle_diameter_mm = nozzle
        generated = generate_settings(intent, printer, filament, nozzle)
        generated.nozzle_size_mm = nozzle
        universal = _universal_settings(generated)
        report = _settings_report(document.process, universal, context)
        return TranslationOutcome(replace(document, process=universal), report.with_weighted_score(), TargetArtifacts(generated, printer, filament))


def _legacy_geometry(document: Universal3MFDocument) -> ParsedModel:
    objects = tuple(
        RawMeshObject(obj.object_id, obj.name, list(obj.mesh.vertices), [triangle.vertices for triangle in obj.mesh.triangles], obj.role.value)
        for obj in document.objects if obj.mesh is not None
    )
    return ParsedModel(list(objects), "millimeter")


def _universal_settings(settings: LegacyPrintSettings) -> PrintSettings:
    return PrintSettings(
        layer_height_mm=settings.layer_height_mm, first_layer_height_mm=settings.first_layer_height_mm,
        wall_count=settings.wall_count, top_layers=settings.top_layers, bottom_layers=settings.bottom_layers,
        infill_density_percent=settings.infill_percent, infill_pattern=settings.infill_pattern,
        print_speed_mm_s=settings.print_speed_mm_s, first_layer_speed_mm_s=settings.first_layer_speed_mm_s,
        nozzle_temperature_c=settings.nozzle_temp_c, bed_temperature_c=settings.bed_temp_c,
        fan_speed_percent=settings.fan_speed_percent, extrusion_width_mm=settings.line_width_mm,
        ironing_enabled=settings.ironing_enabled, seam_position=settings.seam_position,
    )


def _settings_report(source: PrintSettings, target: PrintSettings, context: ConversionContext) -> TranslationReport:
    items: list[TranslationItem] = []
    for feature in ("layer_height_mm", "wall_count", "infill_density_percent", "infill_pattern", "nozzle_temperature_c", "bed_temperature_c", "print_speed_mm_s"):
        before = getattr(source, feature)
        after = getattr(target, feature)
        status = TranslationStatus.SUPPORTED if before == after or before is None else TranslationStatus.APPROXIMATED
        items.append(TranslationItem(
            feature, status, Severity.MEDIUM if status is TranslationStatus.APPROXIMATED else Severity.INFO,
            source_value=None if before is None else str(before), universal_value=None if before is None else str(before),
            target_value=None if after is None else str(after),
            reason=(f"AutoSlice optimized this setting for printer {context.target_printer_id}." if status is TranslationStatus.APPROXIMATED else "Setting is supported by the target profile."),
        ))
    return TranslationReport(tuple(items))
