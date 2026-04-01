"""
AutoSlice — Anycubic 3MF exporter.
Writes a clean, slicer-compatible 3MF:
  · All printable mesh objects are merged into a single <object> (no part splits)
  · OrcaSlicer / Anycubic Slicer Next print settings injected
  · [Content_Types].xml and _rels/.rels regenerated for correctness
"""

import zipfile
from pathlib import Path

import numpy as np

from app.models.print_settings import PrintSettings
from app.models.printer import PrinterProfile, FilamentType
from app.ingestion.unpacker import UnpackedArchive
from app.parser.model_parser import ParsedModel
from app.export.xml_builder import (
    build_settings_configs,
    build_3mf_xml,
    build_content_types_xml,
    build_rels_xml,
)

# Files we drop from the original archive and replace with our own versions.
_SKIP_EXACT = {
    "Metadata/BambuStudio.config",
    "Metadata/Slic3r_PE.config",
    "Metadata/project_settings.config",
    "Metadata/AnycubicSlicer.config",
    "Metadata/slice_info.config",
    # Regenerated to ensure correctness
    "[Content_Types].xml",
    "_rels/.rels",
}
_SKIP_PREFIXES = (
    "Metadata/process_settings_",
    "Metadata/filament_settings_",
    "Metadata/machine_settings_",
)


def export(
    archive: UnpackedArchive,
    settings: PrintSettings,
    printer: PrinterProfile,
    filament_type: FilamentType,
    output_path: Path,
    rotation_matrix: np.ndarray | None = None,
    parsed_model: ParsedModel | None = None,
) -> Path:
    """
    Build the output .3mf:
      1. Copy non-geometry files from the original archive (thumbnails, etc.)
      2. Write a freshly generated, merged 3D/3dmodel.model (single <object>)
         — all printable parts merged, rotation applied at vertex level
      3. Regenerate [Content_Types].xml and _rels/.rels for correctness
      4. Inject Anycubic Slicer Next print-settings configs
    """
    configs = build_settings_configs(settings, printer, filament_type)

    # Generate merged model XML (rotation handled inside build_3mf_xml)
    if parsed_model is not None:
        model_xml = build_3mf_xml(parsed_model, rotation_matrix=rotation_matrix)
    else:
        model_xml = None  # fallback: keep original model files below

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in archive.all_files:
            if not f.is_file():
                continue
            rel     = f.relative_to(archive.extract_dir)
            rel_str = rel.as_posix()

            # Always skip slicer configs and files we regenerate
            if rel_str in _SKIP_EXACT or rel_str.startswith(_SKIP_PREFIXES):
                continue

            # Skip all .model files — either we write our own or fall back below
            if f.suffix.lower() == ".model":
                continue

            zf.write(str(f), rel_str)

        # Write merged model (preferred) or fall back to rotating original files
        if model_xml is not None:
            zf.writestr("3D/3dmodel.model", model_xml)
        else:
            # Fallback path: no parsed_model available — copy originals with rotation
            from app.export.mesh_transform import rotate_model_xml
            for f in archive.all_files:
                if f.is_file() and f.suffix.lower() == ".model":
                    rel_str = f.relative_to(archive.extract_dir).as_posix()
                    raw = f.read_bytes()
                    if rotation_matrix is not None:
                        raw = rotate_model_xml(raw, rotation_matrix)
                    zf.writestr(rel_str, raw)

        # Regenerated infrastructure files
        zf.writestr("[Content_Types].xml", build_content_types_xml())
        zf.writestr("_rels/.rels",         build_rels_xml())

        # Print-settings configs
        for zip_path, content in configs.items():
            zf.writestr(zip_path, content)

    return output_path
