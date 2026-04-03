"""
AutoSlice — Anycubic 3MF exporter.
Copies the original model files unchanged (applying optional rotation) and
injects OrcaSlicer-compatible print settings into the Metadata configs.

The original model geometry is preserved as-is so the slicer can always open
the file.  Rotation is applied at the XML vertex level via mesh_transform.
"""

import zipfile
from pathlib import Path

import numpy as np

from app.models.print_settings import PrintSettings
from app.models.printer import PrinterProfile, FilamentType
from app.ingestion.unpacker import UnpackedArchive
from app.parser.model_parser import ParsedModel
from app.export.xml_builder import build_settings_configs
from app.export.mesh_transform import rotate_model_xml, normalize_model_xml

# Slicer-specific config files we strip out and replace with our own.
# We use a prefix match for process/filament/machine settings (Bambu numbers them _1, _2, etc.)
_SKIP_EXACT = {
    "Metadata/BambuStudio.config",
    "Metadata/Slic3r_PE.config",
    "Metadata/project_settings.config",
    "Metadata/AnycubicSlicer.config",
    "Metadata/slice_info.config",
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
    parsed_model: ParsedModel | None = None,   # reserved for future merge pass
) -> Path:
    """
    Build the output .3mf by:
      1. Copying every file from the original archive (preserving geometry)
      2. If rotation_matrix is provided, rotating vertex coordinates in all
         .model files so the output is pre-oriented for the slicer
      3. Dropping Bambu/slicer-specific metadata configs
      4. Injecting our Metadata configs with generated print settings
    """
    configs = build_settings_configs(settings, printer, filament_type)

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in archive.all_files:
            if not f.is_file():
                continue
            rel     = f.relative_to(archive.extract_dir)
            rel_str = rel.as_posix()

            if rel_str in _SKIP_EXACT or rel_str.startswith(_SKIP_PREFIXES):
                continue

            # Apply orientation rotation to model geometry files, or normalize
            # item transforms so Anycubic Slicer receives correctly assembled parts
            if f.suffix.lower() == ".model":
                raw = f.read_bytes()
                if rotation_matrix is not None:
                    modified = rotate_model_xml(raw, rotation_matrix)
                else:
                    modified = normalize_model_xml(raw)
                zf.writestr(rel_str, modified)
            else:
                zf.write(str(f), rel_str)

        for zip_path, content in configs.items():
            zf.writestr(zip_path, content)

    return output_path
