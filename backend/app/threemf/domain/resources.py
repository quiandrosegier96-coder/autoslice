"""3MF resources, textures, and preservation payloads."""

from dataclasses import dataclass
from enum import Enum

from app.threemf.domain.materials import MaterialGroup


@dataclass(frozen=True)
class TextureResource:
    resource_id: str
    path: str
    payload: bytes | None = None
    content_type: str | None = None
    tile_style_u: str | None = None
    tile_style_v: str | None = None
    box: str | None = None


@dataclass(frozen=True)
class TextureCoordinate:
    u: float
    v: float


@dataclass(frozen=True)
class TextureGroup:
    resource_id: str
    texture_resource_id: str
    coordinates: tuple[TextureCoordinate, ...] = ()


class PreservationPolicy(str, Enum):
    SAFE_TO_COPY = "safe_to_copy"
    SOURCE_ONLY = "source_only"
    DROP_ON_CROSS_SLICER = "drop_on_cross_slicer"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True)
class OpaqueResource:
    identifier: str
    source: str
    path: str
    payload: bytes
    namespace: str | None = None
    content_type: str | None = None
    policy: PreservationPolicy = PreservationPolicy.REVIEW_REQUIRED


@dataclass(frozen=True)
class Resources:
    material_groups: tuple[MaterialGroup, ...] = ()
    textures: tuple[TextureResource, ...] = ()
    texture_groups: tuple[TextureGroup, ...] = ()
    opaque: tuple[OpaqueResource, ...] = ()
