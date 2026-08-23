"""Slicer-neutral intelligence models. All collections are immutable for determinism."""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RulePriority(IntEnum):
    PREFERENCE = 10
    PERFORMANCE = 20
    QUALITY = 30
    COMPATIBILITY = 40
    HARD_LIMIT = 50
    SAFETY = 60


class PlanStatus(str, Enum):
    WITHIN_BUILD_VOLUME = "within_build_volume"
    NEAR_LIMIT = "near_limit"
    OUTSIDE_BUILD_VOLUME = "outside_build_volume"


class OptimizationMode(str, Enum):
    BALANCED = "balanced"
    QUALITY_FIRST = "quality_first"
    FAST_PRINT = "fast_print"
    MATERIAL_SAVING = "material_saving"


class OrientationMode(str, Enum):
    AUTO = "auto"
    PRESERVE = "preserve"
    MANUAL = "manual"


@dataclass(frozen=True)
class AutoSliceProfile:
    mode: OptimizationMode = OptimizationMode.BALANCED
    orientation_mode: OrientationMode = OrientationMode.AUTO
    orientation_confidence_threshold: Confidence = Confidence.HIGH
    orientation_improvement_threshold: float = 10.0
    overhang_threshold_degrees: float = 45.0


@dataclass(frozen=True)
class NozzleProfile:
    diameter_mm: float
    material: str = "brass"
    minimum_layer_height_mm: float = 0.08
    maximum_layer_height_mm: float = 0.28
    recommended_layer_height_mm: float = 0.2
    line_width_range_mm: tuple[float, float] = (0.36, 0.48)


@dataclass(frozen=True)
class FilamentProfile:
    material_id: str
    temperature_range_c: tuple[int, int]
    bed_temperature_range_c: tuple[int, int]
    max_flow_mm3_s: float
    cooling_range_percent: tuple[int, int]
    density_g_cm3: float
    recommended_speed_mm_s: tuple[float, float]
    compatible_nozzle_materials: tuple[str, ...] = ("brass", "hardened_steel")


@dataclass(frozen=True)
class PrinterProfile:
    printer_id: str
    display_name: str
    build_volume_mm: tuple[float, float, float]
    nozzle_profiles: tuple[NozzleProfile, ...]
    supported_materials: tuple[str, ...]
    temperature_limits_c: tuple[int, int]
    speed_limit_mm_s: float
    acceleration_limit_mm_s2: float
    capabilities: tuple[str, ...]
    max_tools: int = 1
    defaults: tuple[tuple[str, Any], ...] = ()
    support_types: tuple[str, ...] = ("normal", "tree")
    minimum_object_spacing_mm: float | None = None


@dataclass(frozen=True)
class TargetProfile:
    slicer: str
    printer: PrinterProfile
    nozzle: NozzleProfile
    filament: FilamentProfile


@dataclass(frozen=True)
class ObjectAnalysis:
    object_id: str
    dimensions_mm: tuple[float, float, float]
    bounding_box_mm: tuple[tuple[float, float, float], tuple[float, float, float]]
    volume_mm3: float
    surface_area_mm2: float
    material_id: str | None
    thin_feature_warning: bool = False


@dataclass(frozen=True)
class ProjectAnalysis:
    object_count: int
    dimensions_mm: tuple[float, float, float]
    bounding_box_mm: tuple[tuple[float, float, float], tuple[float, float, float]]
    total_geometry_volume_mm3: float
    surface_area_mm2: float
    material_ids: tuple[str, ...]
    object_material_mapping: tuple[tuple[str, str | None], ...]
    settings: tuple[tuple[str, Any], ...]
    objects: tuple[ObjectAnalysis, ...]
    build_volume_status: PlanStatus | None = None
    overhang_indicator: bool = False
    small_feature_indicator: bool = False


@dataclass(frozen=True)
class OptimizationChange:
    setting: str
    old_value: Any
    new_value: Any
    reason: str
    rule: str
    confidence: Confidence
    priority: RulePriority
    category: str


@dataclass(frozen=True)
class PlanMessage:
    code: str
    message: str
    rule: str
    priority: RulePriority
    confidence: Confidence = Confidence.HIGH


@dataclass(frozen=True)
class OrientationRecommendation:
    rotation_degrees: tuple[float, float, float]
    reason: str
    confidence: Confidence
    apply_automatically: bool = False


@dataclass(frozen=True)
class SupportRecommendation:
    reason: str
    confidence: Confidence
    apply_automatically: bool = False


@dataclass(frozen=True)
class CompatibilityBreakdown:
    source_compatibility: float
    target_compatibility: float
    optimization_impact: float
    final_compatibility: float
    supported_percent: float
    approximated_percent: float
    preserved_percent: float
    unsupported_percent: float


@dataclass(frozen=True)
class OptimizationPlan:
    changes: tuple[OptimizationChange, ...] = ()
    unchanged: tuple[str, ...] = ()
    warnings: tuple[PlanMessage, ...] = ()
    blocked: tuple[PlanMessage, ...] = ()
    recommendations: tuple[PlanMessage, ...] = ()
    geometry_changes: tuple["GeometryTransformChange", ...] = ()
    support_changes: tuple["SupportChange", ...] = ()
    placement_changes: tuple["PlacementChange", ...] = ()
    compatibility: CompatibilityBreakdown = field(
        default_factory=lambda: CompatibilityBreakdown(100, 100, 100, 100, 100, 0, 0, 0)
    )

    @property
    def can_convert(self) -> bool:
        return not self.blocked

    def change_for(self, setting: str) -> OptimizationChange | None:
        return next((change for change in self.changes if change.setting == setting), None)


@dataclass(frozen=True)
class GeometryTransformChange:
    object_id: str
    current_transform: tuple[float, ...]
    recommended_transform: tuple[float, ...]
    rotation_degrees: tuple[float, float, float]
    reason: str
    rule: str
    confidence: Confidence
    score_improvement: float
    applied: bool


@dataclass(frozen=True)
class SupportChange:
    setting: str
    old_value: Any
    new_value: Any
    reason: str
    rule: str
    confidence: Confidence
    applied: bool


@dataclass(frozen=True)
class PlacementChange:
    item_index: int
    object_id: str
    old_transform: tuple[float, ...]
    new_transform: tuple[float, ...]
    old_position_mm: tuple[float, float, float]
    new_position_mm: tuple[float, float, float]
    reason: str
    rule: str
    confidence: Confidence
    applied: bool
