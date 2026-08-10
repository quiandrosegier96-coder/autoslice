"""Build items and slicer plate structure."""

from dataclasses import dataclass, field

from app.threemf.domain.geometry import Transform


@dataclass(frozen=True)
class BuildItem:
    object_id: str
    transform: Transform = field(default_factory=Transform)
    plate_id: str | None = None
    part_number: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Plate:
    plate_id: str
    name: str = ""
    build_item_indices: tuple[int, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Build:
    items: tuple[BuildItem, ...] = ()
    plates: tuple[Plate, ...] = ()
