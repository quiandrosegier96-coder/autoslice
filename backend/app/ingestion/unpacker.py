"""
AutoSlice — 3MF unpacker.
Extracts the ZIP archive and maps its contents to known 3MF paths.
"""

from pathlib import Path
from dataclasses import dataclass, field

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.container.xml import parse_xml


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

# OPC relationship type for the primary 3D model
_3MF_REL_TYPE = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"


def _parse_rels(rels_path: Path) -> str | None:
    """
    Parse _rels/.rels to discover the actual 3D model file path.
    Returns the relative path string (without leading slash), or None.
    """
    if not rels_path.exists():
        return None
    try:
        root = parse_xml(rels_path.read_bytes(), str(rels_path))
        for rel in root:
            tag = rel.tag.split("}")[-1] if "}" in rel.tag else rel.tag
            if tag == "Relationship":
                if rel.attrib.get("Type", "") == _3MF_REL_TYPE:
                    target = rel.attrib.get("Target", "").lstrip("/")
                    if target:
                        return target
    except Exception:
        pass
    return None

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
        root = parse_xml(config_path.read_bytes(), str(config_path))
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
    container = ThreeMFContainer.from_path(archive_path)
    all_names = list(container.paths)
    resolved_root = extract_dir.resolve()
    for name in all_names:
        destination = (extract_dir / name).resolve()
        if destination != resolved_root and resolved_root not in destination.parents:
            raise ValueError(f"Unsafe extraction target: {name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(container.read(name))

    all_files = [extract_dir / name for name in all_names]

    # Discover the primary model file from _rels/.rels (authoritative for non-Bambu 3MFs)
    discovered = _parse_rels(extract_dir / "_rels" / ".rels")
    if discovered:
        candidate = extract_dir / discovered
        model_file = candidate if candidate.exists() else extract_dir / _MODEL_PATH
    else:
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
