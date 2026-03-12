"""
AutoSlice — 3MF unpacker.
Extracts the ZIP archive and maps its contents to known 3MF paths.
"""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from dataclasses import dataclass, field


# Well-known paths inside a 3MF archive
_MODEL_PATH = "3D/3dmodel.model"
_CONTENT_TYPES_PATH = "[Content_Types].xml"
_RELS_PATH = "_rels/.rels"
_BAMBU_CONFIG_PATHS = [
    "Metadata/model_settings.config",
    "Metadata/BambuStudio.config",
    "Metadata/Slic3r_PE.config",
]
_BAMBU_OBJECT_CONFIG = "Metadata/model_settings.config"

# Bambu object subtypes that should NOT be printed
_NON_PRINTABLE_SUBTYPES = {"negative_volume", "modifier", "support_blocker", "support_enforcer"}


def _parse_object_type_map(config_path: Path) -> dict[str, str]:
    """
    Parse Metadata/model_settings.config to build {object_id: subtype} map.
    Returns empty dict if file is missing or unparseable.
    """
    if not config_path.exists():
        return {}
    try:
        tree = ET.parse(config_path)
        root = tree.getroot()
        result: dict[str, str] = {}
        for obj_el in root.iter("object"):
            for part_el in obj_el.iter("part"):
                part_id = part_el.attrib.get("id", "")
                subtype = part_el.attrib.get("subtype", "part")
                if part_id:
                    result[part_id] = subtype
        return result
    except Exception:
        return {}


@dataclass
class UnpackedArchive:
    extract_dir: Path
    model_file: Path | None           # 3D/3dmodel.model (main scene graph)
    model_files: list[Path]           # ALL .model files (includes Objects/ sub-files)
    content_types_file: Path | None   # [Content_Types].xml
    object_type_map: dict[str, str] = field(default_factory=dict)  # {object_id: subtype}
    metadata_files: list[Path] = field(default_factory=list)
    thumbnail_files: list[Path] = field(default_factory=list)
    all_files: list[Path] = field(default_factory=list)


def unpack(archive_path: Path, extract_dir: Path) -> UnpackedArchive:
    """
    Extract a .3mf ZIP archive to extract_dir.
    Returns an UnpackedArchive mapping key files to their extracted paths.
    """
    with zipfile.ZipFile(archive_path, "r") as zf:
        zf.extractall(extract_dir)
        all_names = zf.namelist()

    all_files = [extract_dir / name for name in all_names]

    model_file = extract_dir / _MODEL_PATH
    content_types_file = extract_dir / _CONTENT_TYPES_PATH

    metadata_files = [
        extract_dir / p for p in _BAMBU_CONFIG_PATHS
        if (extract_dir / p).exists()
    ]

    thumbnail_files = [
        f for f in all_files
        if f.suffix.lower() in {".png", ".jpg", ".jpeg"}
    ]

    model_files = [f for f in all_files if f.suffix == ".model" and f.is_file()]

    object_type_map = _parse_object_type_map(extract_dir / _BAMBU_OBJECT_CONFIG)

    return UnpackedArchive(
        extract_dir=extract_dir,
        model_file=model_file if model_file.exists() else None,
        model_files=model_files,
        content_types_file=content_types_file if content_types_file.exists() else None,
        object_type_map=object_type_map,
        metadata_files=metadata_files,
        thumbnail_files=thumbnail_files,
        all_files=all_files,
    )
