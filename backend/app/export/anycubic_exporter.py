"""
AutoSlice — Anycubic 3MF exporter.
Copies the original model files unchanged and injects OrcaSlicer-compatible
print settings into Metadata/project_settings.config.
"""

import zipfile
from pathlib import Path

from app.models.print_settings import PrintSettings
from app.models.printer import PrinterProfile, FilamentType
from app.ingestion.unpacker import UnpackedArchive
from app.export.xml_builder import build_settings_configs

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
) -> Path:
    """
    Build the output .3mf by:
      1. Copying every file from the original archive as-is (preserving geometry exactly)
      2. Dropping Bambu/slicer-specific metadata configs
      3. Injecting our Metadata/project_settings.config with the generated print settings
    """
    configs = build_settings_configs(settings, printer, filament_type)

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
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

    return output_path
