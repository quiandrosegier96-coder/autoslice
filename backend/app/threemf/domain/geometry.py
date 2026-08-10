"""Geometry, transforms, objects, components, and property assignments."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True)
class Transform:
    """3MF affine transform in row-major 3x4 form."""

    values: tuple[float, ...] = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        if len(self.values) != 12:
            raise ValueError("A 3MF transform must contain exactly 12 values.")

    @classmethod
    def parse(cls, raw: str | None) -> Transform:
        if not raw:
            return cls()
        try:
            return cls(tuple(float(value) for value in raw.split()))
        except ValueError as exc:
            raise ValueError(f"Invalid 3MF transform: {raw!r}") from exc


class ObjectRole(str, Enum):
    MODEL = "model"
    SUPPORT = "support"
    MODIFIER = "modifier"
    NEGATIVE_VOLUME = "negative_volume"
    SUPPORT_BLOCKER = "support_blocker"
    SUPPORT_ENFORCER = "support_enforcer"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Triangle:
    vertices: tuple[int, int, int]
    property_resource_id: str | None = None
    property_indices: tuple[int | None, int | None, int | None] = (None, None, None)


@dataclass(frozen=True)
class Mesh:
    vertices: tuple[tuple[float, float, float], ...] = ()
    triangles: tuple[Triangle, ...] = ()


@dataclass(frozen=True)
class ComponentReference:
    object_id: str
    transform: Transform = field(default_factory=Transform)
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ObjectSettings:
    values: tuple[tuple[str, str], ...] = ()
    opaque_payloads: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelObject:
    object_id: str
    name: str = ""
    object_type: str = "model"
    role: ObjectRole = ObjectRole.MODEL
    mesh: Mesh | None = None
    components: tuple[ComponentReference, ...] = ()
    material_resource_id: str | None = None
    material_index: int | None = None
    settings: ObjectSettings = field(default_factory=ObjectSettings)
    metadata: tuple[tuple[str, str], ...] = ()
    source_path: str = "3D/3dmodel.model"
