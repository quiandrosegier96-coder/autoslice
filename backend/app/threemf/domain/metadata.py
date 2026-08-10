"""Project, source, package, and opaque preservation descriptors."""

from dataclasses import dataclass
from enum import Enum

from app.threemf.domain.resources import OpaqueResource


class SlicerType(str, Enum):
    BAMBU = "bambu"
    ORCA = "orca"
    PRUSA = "prusa"
    ANYCUBIC = "anycubic"
    CURA = "cura"
    CORE = "core"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SourceInfo:
    slicer: SlicerType = SlicerType.UNKNOWN
    version: str | None = None
    confidence: float = 0.0
    detection_evidence: tuple[str, ...] = ()
    original_filename: str = ""


@dataclass(frozen=True)
class PackageInfo:
    primary_model_path: str
    content_types_path: str = "[Content_Types].xml"
    relationships_path: str = "_rels/.rels"
    unit: str = "millimeter"
    paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectMetadata:
    title: str | None = None
    description: str | None = None
    creator: str | None = None
    application: str | None = None
    creation_date: str | None = None
    modification_date: str | None = None
    values: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class PreservationData:
    original_project_name: str | None = None
    opaque_extensions: tuple[OpaqueResource, ...] = ()
