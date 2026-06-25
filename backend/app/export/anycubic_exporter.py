"""
AutoSlice - Anycubic 3MF exporter.

Writes a canonical 3MF package with a guaranteed root model file at
3D/3dmodel.model, then injects OrcaSlicer-compatible print settings.
"""

import zipfile
from pathlib import Path

import numpy as np

from app.models.print_settings import PrintSettings
from app.models.printer import PrinterProfile, FilamentType
from app.ingestion.unpacker import UnpackedArchive
from app.parser.model_parser import ParsedModel
from app.export.xml_builder import (
    build_3mf_xml,
    build_content_types_xml,
    build_rels_xml,
    build_settings_configs,
    build_model_settings_config,
)

# Slicer-specific config files we strip out and replace with our own.
# We use a prefix match for process/filament/machine settings.
_SKIP_EXACT = {
    "[Content_Types].xml",
    "_rels/.rels",
    "3D/3dmodel.model",
    "Metadata/BambuStudio.config",
    "Metadata/Slic3r_PE.config",
    "Metadata/project_settings.config",
    "Metadata/AnycubicSlicer.config",
    "Metadata/slice_info.config",
}
_SKIP_PREFIXES = (
    "3D/",
    "Metadata/process_settings_",
    "Metadata/filament_settings_",
    "Metadata/machine_settings_",
)
_NON_PRINTABLE = {"negative_volume", "modifier", "support_blocker", "support_enforcer"}


def _has_printable_geometry(parsed_model: ParsedModel | None) -> bool:
    if parsed_model is None:
        return False
    for obj in parsed_model.objects:
        if obj.object_type in _NON_PRINTABLE:
            continue
        if obj.vertices and obj.triangles:
            return True
    return False


def export(
    archive: UnpackedArchive,
    settings: PrintSettings,
    printer: PrinterProfile,
    filament_type: FilamentType,
    output_path: Path,
    rotation_matrix: np.ndarray | None = None,
    parsed_model: ParsedModel | None = None,
    scale_factor: float = 1.0,
) -> Path:
    """
    Build the output .3mf by:
      1. Writing a clean root OPC relationship and root 3MF model file
      2. Preserving useful non-model assets from the original archive
      3. Dropping Bambu/slicer-specific metadata configs
      4. Injecting our Metadata configs with generated print settings
    """
    if not _has_printable_geometry(parsed_model):
        raise ValueError("No printable mesh geometry found for export.")

    configs = build_settings_configs(settings, printer, filament_type)
    model_xml = build_3mf_xml(parsed_model, rotation_matrix, scale_factor)

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", build_content_types_xml())
        zf.writestr("_rels/.rels", build_rels_xml())
        zf.writestr("3D/3dmodel.model", model_xml)

        for f in archive.all_files:
            if not f.is_file():
                continue
            rel = f.relative_to(archive.extract_dir)
            rel_str = rel.as_posix()

            if rel_str in _SKIP_EXACT or rel_str.startswith(_SKIP_PREFIXES):
                continue

            zf.write(str(f), rel_str)

        for zip_path, content in configs.items():
            zf.writestr(zip_path, content)

        # Inject object-to-filament-slot assignment when multicolor is active.
        if settings.color_count > 1 and parsed_model is not None:
            model_settings_xml = build_model_settings_config(parsed_model, settings.color_count)
            zf.writestr("Metadata/model_settings.config", model_settings_xml)

    return output_path
