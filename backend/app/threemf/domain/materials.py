"""Semantic materials and physical filament/tool assignments."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Material:
    material_id: str
    name: str = ""
    material_type: str | None = None
    filament_type: str | None = None
    color: str | None = None
    diameter_mm: float | None = None
    nozzle_temperature_c: int | None = None
    bed_temperature_c: int | None = None
    density_g_cm3: float | None = None
    manufacturer: str | None = None
    brand: str | None = None
    properties: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class MaterialGroup:
    resource_id: str
    display_name: str = ""
    materials: tuple[Material, ...] = ()


@dataclass(frozen=True)
class ToolAssignment:
    """A physical spool/tool slot; deliberately separate from material identity."""

    tool_index: int
    material_id: str | None = None
    color: str | None = None
    filament_type: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()
