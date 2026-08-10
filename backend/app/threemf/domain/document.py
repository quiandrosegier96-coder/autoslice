"""Universal3MF v1 aggregate root."""

from dataclasses import dataclass, field

from app.threemf.domain.build import Build
from app.threemf.domain.geometry import ModelObject
from app.threemf.domain.materials import Material, ToolAssignment
from app.threemf.domain.metadata import PackageInfo, PreservationData, ProjectMetadata, SourceInfo
from app.threemf.domain.resources import Resources
from app.threemf.domain.settings import PrintSettings
from app.threemf.domain.supports import SupportConfig


@dataclass(frozen=True)
class PrinterInfo:
    printer_id: str | None = None
    display_name: str | None = None
    nozzle_size_mm: float | None = None
    build_volume_mm: tuple[float, float, float] | None = None
    source_values: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Universal3MFDocument:
    schema_version: str
    source: SourceInfo
    package: PackageInfo
    metadata: ProjectMetadata = field(default_factory=ProjectMetadata)
    resources: Resources = field(default_factory=Resources)
    objects: tuple[ModelObject, ...] = ()
    build: Build = field(default_factory=Build)
    process: PrintSettings = field(default_factory=PrintSettings)
    materials: tuple[Material, ...] = ()
    tool_assignments: tuple[ToolAssignment, ...] = ()
    supports: SupportConfig = field(default_factory=SupportConfig)
    printer: PrinterInfo = field(default_factory=PrinterInfo)
    preservation: PreservationData = field(default_factory=PreservationData)

    def __post_init__(self) -> None:
        object_ids = [obj.object_id for obj in self.objects]
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("Universal3MF object IDs must be unique.")
        known = set(object_ids)
        dangling = [
            component.object_id for obj in self.objects for component in obj.components
            if component.object_id not in known
        ] + [item.object_id for item in self.build.items if item.object_id not in known]
        if dangling:
            raise ValueError(f"Universal3MF contains dangling object references: {sorted(set(dangling))}")
