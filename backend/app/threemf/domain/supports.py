"""Source support semantics; generation engines remain outside this model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SupportRegion:
    target_object_id: str | None = None
    kind: str = "painted"
    payload: bytes | None = None
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SupportConfig:
    enabled: bool | None = None
    support_type: str | None = None
    placement: str | None = None
    overhang_angle_deg: float | None = None
    density_percent: float | None = None
    interface_layers: int | None = None
    regions: tuple[SupportRegion, ...] = ()
    source_values: tuple[tuple[str, str], ...] = ()
