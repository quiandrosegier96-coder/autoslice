"""
AutoSlice — General metadata extractor.
Collects high-level facts from the unpacked archive before full parsing.
"""

from pathlib import Path
from dataclasses import dataclass


@dataclass
class ArchiveMetadata:
    original_filename: str
    size_bytes: int
    has_model_file: bool
    has_thumbnail: bool
    all_file_paths: list[str]   # relative paths inside the archive


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
