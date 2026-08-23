"""Optional, slicer-neutral print and conversion settings."""

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True)
class RetractionSettings:
    length_mm: float | None = None
    speed_mm_s: float | None = None
    z_hop_mm: float | None = None


@dataclass(frozen=True)
class AdhesionSettings:
    brim_width_mm: float | None = None
    skirt_loops: int | None = None
    raft_layers: int | None = None


@dataclass(frozen=True)
class PrintSettings:
    layer_height_mm: float | None = None
    first_layer_height_mm: float | None = None
    wall_count: int | None = None
    top_layers: int | None = None
    bottom_layers: int | None = None
    infill_density_percent: float | None = None
    infill_pattern: str | None = None
    print_speed_mm_s: float | None = None
    travel_speed_mm_s: float | None = None
    first_layer_speed_mm_s: float | None = None
    nozzle_temperature_c: int | None = None
    bed_temperature_c: int | None = None
    fan_speed_percent: int | None = None
    flow_percent: float | None = None
    extrusion_width_mm: float | None = None
    retraction: RetractionSettings = field(default_factory=RetractionSettings)
    adhesion: AdhesionSettings = field(default_factory=AdhesionSettings)
    ironing_enabled: bool | None = None
    seam_position: str | None = None
    acceleration_mm_s2: float | None = None
    jerk_mm_s: float | None = None
    variable_layer_height: bool | None = None
    adaptive_layer_profile: tuple[tuple[float, float], ...] = ()
    source_values: tuple[tuple[str, str], ...] = ()


class ConversionMode(str, Enum):
    PRESERVE_SOURCE = "preserve_source"
    PRESERVE = "preserve_source"
    AUTOSLICE = "autoslice"


@dataclass(frozen=True)
class ConversionContext:
    target_slicer: str
    target_printer_id: str | None = None
    nozzle_size_mm: float | None = None
    material_id: str | None = None
    mode: ConversionMode = ConversionMode.AUTOSLICE
    source_slicer: str | None = None
    preserve_source: bool = False
    optimize_for_target: bool = True
    optimization_profile: str = "balanced"
