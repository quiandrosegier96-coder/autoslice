"""Small, reliable profile catalogue backed by existing printer data."""

from app.rules.printer_loader import load_printer_profile
from app.threemf.intelligence.models import (
    FilamentProfile,
    NozzleProfile,
    PrinterProfile,
    TargetProfile,
)

_FILAMENTS = {
    "pla": FilamentProfile("pla", (190, 230), (45, 65), 18.0, (60, 100), 1.24, (40, 250)),
    "petg": FilamentProfile("petg", (220, 260), (65, 90), 14.0, (20, 60), 1.27, (35, 180)),
    "tpu": FilamentProfile("tpu", (210, 240), (35, 60), 5.0, (20, 80), 1.21, (15, 60)),
}


def nozzle_profile(
    diameter_mm: float,
    minimum: float | None = None,
    maximum: float | None = None,
    material: str = "brass",
) -> NozzleProfile:
    minimum = minimum if minimum is not None else round(diameter_mm * 0.2, 3)
    maximum = maximum if maximum is not None else round(diameter_mm * 0.7, 3)
    recommended = round(diameter_mm * 0.5, 3)
    return NozzleProfile(
        diameter_mm,
        material,
        minimum,
        maximum,
        recommended,
        (round(diameter_mm * 0.9, 3), round(diameter_mm * 1.2, 3)),
    )


def build_target_profile(
    slicer: str,
    printer_id: str,
    nozzle_size_mm: float = 0.4,
    material_id: str = "pla",
    nozzle_material: str = "brass",
) -> TargetProfile:
    legacy = load_printer_profile(printer_id)
    material_key = material_id.lower()
    if material_key not in _FILAMENTS:
        raise ValueError(f"Unknown filament profile: '{material_id}'")
    nozzle = nozzle_profile(
        nozzle_size_mm, legacy.min_layer_height_mm, legacy.max_layer_height_mm, nozzle_material
    )
    printer = PrinterProfile(
        legacy.id,
        legacy.display_name,
        (legacy.build_volume_x_mm, legacy.build_volume_y_mm, legacy.build_volume_z_mm),
        (nozzle,),
        tuple(sorted(item.value for item in legacy.supported_filaments)),
        (0, 300),
        legacy.max_speed_mm_s,
        legacy.max_acceleration_xy,
        tuple(
            sorted(
                ("heated_bed", "variable_layer_height")
                + (("multi_material",) if legacy.max_colors > 1 else ())
            )
        ),
        legacy.max_colors,
    )
    return TargetProfile(slicer.lower(), printer, nozzle, _FILAMENTS[material_key])
