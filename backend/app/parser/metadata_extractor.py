"""
AutoSlice — General metadata extractor.
Collects high-level facts from the unpacked archive before full parsing.
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class ArchiveMetadata:
    original_filename: str
    size_bytes: int
    has_model_file: bool
    has_thumbnail: bool
    all_file_paths: list[str]   # relative paths inside the archive


@dataclass
class SourceFilamentInfo:
    """Filament color/type data read from the source 3MF metadata."""
    colors: list[str] = field(default_factory=list)   # hex strings e.g. "#FF0000"
    types:  list[str] = field(default_factory=list)   # e.g. "PLA", "PETG"
    count:  int       = 1


def _clean_color(raw: str) -> str:
    """Normalize a color string — strip whitespace, trailing semicolons, ensure '#' prefix."""
    c = raw.strip().rstrip(";").strip()
    if c and not c.startswith("#"):
        c = "#" + c
    # Validate hex — if garbage, return fallback
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", c):
        return c
    return "#FF0000"


def _type_to_autoslice(raw: str) -> str:
    """Map slicer type strings to AutoSlice internal IDs (pla/petg/tpu)."""
    t = raw.strip().lower()
    if "petg" in t:
        return "petg"
    if "tpu" in t or "tpe" in t or "flex" in t:
        return "tpu"
    return "pla"


def extract_source_filaments(extract_dir: Path) -> SourceFilamentInfo:
    """
    Read filament colors and types from the source 3MF's project_settings.config.
    Handles Bambu Studio JSON format (filament_colour may have trailing semicolons).
    Returns SourceFilamentInfo with empty lists if metadata is absent or unreadable.
    """
    config_path = extract_dir / "Metadata" / "project_settings.config"
    if not config_path.exists():
        return SourceFilamentInfo()

    try:
        data = json.loads(config_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return SourceFilamentInfo()

    raw_colors = data.get("filament_colour", [])
    raw_types  = data.get("filament_type",  [])

    # Both fields are either lists or semicolon-separated strings in some Bambu versions
    if isinstance(raw_colors, str):
        raw_colors = [c for c in raw_colors.split(";") if c.strip()]
    if isinstance(raw_types, str):
        raw_types = [t for t in raw_types.split(";") if t.strip()]

    colors = [_clean_color(c) for c in raw_colors if c.strip()]
    types  = [_type_to_autoslice(t) for t in raw_types]

    if not colors:
        return SourceFilamentInfo()

    # Pad types to match color count if needed
    while len(types) < len(colors):
        types.append("pla")

    return SourceFilamentInfo(
        colors=colors,
        types=types[:len(colors)],
        count=len(colors),
    )


def extract_archive_metadata(
    original_filename: str,
    size_bytes: int,
    extract_dir: Path,
    all_files: list[Path],
) -> ArchiveMetadata:
    """
    Build a quick overview of what the archive contains.
    Used in the upload response so the frontend can show basic info immediately.
    """
    model_file = extract_dir / "3D" / "3dmodel.model"
    thumbnails = [f for f in all_files if f.suffix.lower() in {".png", ".jpg", ".jpeg"}]
    relative_paths = [str(f.relative_to(extract_dir)) for f in all_files]

    return ArchiveMetadata(
        original_filename=original_filename,
        size_bytes=size_bytes,
        has_model_file=model_file.exists(),
        has_thumbnail=len(thumbnails) > 0,
        all_file_paths=relative_paths,
    )
