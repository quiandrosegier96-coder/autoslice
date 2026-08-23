"""Shared semantic mapping for PrusaSlicer-family JSON project settings."""

from __future__ import annotations

import json

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.container.xml import local_name, parse_xml
from app.threemf.domain.materials import Material, ToolAssignment
from app.threemf.domain.settings import AdhesionSettings, PrintSettings, RetractionSettings

PROJECT_SETTINGS_PATH = "Metadata/project_settings.config"
PRUSA_SETTINGS_PATH = "Metadata/Slic3r_PE.config"


def read_project_settings(container: ThreeMFContainer) -> dict[str, object]:
    result: dict[str, object] = {}
    if container.exists(PRUSA_SETTINGS_PATH):
        result.update(_read_prusa_settings(container.read(PRUSA_SETTINGS_PATH)))
    if container.exists(PROJECT_SETTINGS_PATH):
        try:
            value = json.loads(container.read(PROJECT_SETTINGS_PATH).decode("utf-8", errors="replace"))
            if isinstance(value, dict):
                result.update(value)
        except (ValueError, TypeError):
            pass
    return result


def _read_prusa_settings(payload: bytes) -> dict[str, object]:
    """Read the metadata-key XML or INI-like variants seen in Prusa-family packages."""
    values: dict[str, object] = {}
    if payload.lstrip().startswith(b"<"):
        root = parse_xml(payload, PRUSA_SETTINGS_PATH)
        for element in root.iter():
            if local_name(element.tag) != "metadata":
                continue
            key = element.attrib.get("key") or element.attrib.get("name")
            if key:
                values[key] = element.attrib.get("value", element.text or "")
        return values
    for line in payload.decode("utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";", "[")) or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip():
            values[key.strip()] = value.strip()
    return values


def _first(value: object) -> object | None:
    return value[0] if isinstance(value, list) and value else value


def _float(value: object) -> float | None:
    try:
        raw = _first(value)
        return float(str(raw).rstrip("%")) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _int(value: object) -> int | None:
    parsed = _float(value)
    return int(parsed) if parsed is not None else None


def _bool(value: object) -> bool | None:
    raw = _first(value)
    if raw in (True, "1", 1, "true", "True"):
        return True
    if raw in (False, "0", 0, "false", "False"):
        return False
    return None


def _str(value: object) -> str | None:
    raw = _first(value)
    return str(raw) if raw not in (None, "") else None


def _value(data: dict[str, object], *semantic_aliases: str) -> object | None:
    return next((data[key] for key in semantic_aliases if key in data), None)


def settings_from_project(data: dict[str, object]) -> PrintSettings:
    known = {
        "layer_height", "initial_layer_print_height", "wall_loops", "top_shell_layers",
        "bottom_shell_layers", "sparse_infill_density", "sparse_infill_pattern",
        "outer_wall_speed", "travel_speed", "initial_layer_speed", "nozzle_temperature",
        "bed_temperature", "fan_max_speed", "flow_ratio", "line_width", "retraction_length",
        "retraction_speed", "z_hop", "brim_width", "skirt_loops", "raft_layers",
        "ironing_type", "seam_position", "default_acceleration", "jerk_print",
        "enable_prime_tower", "variable_layer_height", "first_layer_height", "perimeters",
        "top_solid_layers", "bottom_solid_layers", "fill_density", "fill_pattern",
        "perimeter_speed", "temperature", "max_fan_speed", "extrusion_width",
        "retract_length", "retract_speed", "retract_lift", "skirts", "ironing", "first_layer_speed",
        "layer_height_0", "wall_line_count", "top_layers", "bottom_layers", "infill_sparse_density",
        "speed_print", "speed_travel", "speed_layer_0", "material_print_temperature",
        "material_bed_temperature", "cool_fan_speed", "line_width", "retraction_hop",
        "adhesion_type", "z_seam_type", "acceleration_print", "support_enable",
    }
    ironing = _str(data.get("ironing_type"))
    flow = _float(data.get("flow_ratio"))
    return PrintSettings(
        layer_height_mm=_float(_value(data, "layer_height")),
        first_layer_height_mm=_float(_value(data, "layer_height_0", "first_layer_height", "initial_layer_print_height")),
        wall_count=_int(_value(data, "wall_line_count", "perimeters", "wall_loops")), top_layers=_int(_value(data, "top_layers", "top_solid_layers", "top_shell_layers")),
        bottom_layers=_int(_value(data, "bottom_layers", "bottom_solid_layers", "bottom_shell_layers")),
        infill_density_percent=_float(_value(data, "infill_sparse_density", "fill_density", "sparse_infill_density")),
        infill_pattern=_str(_value(data, "fill_pattern", "sparse_infill_pattern")),
        print_speed_mm_s=_float(_value(data, "speed_print", "perimeter_speed", "outer_wall_speed")), travel_speed_mm_s=_float(_value(data, "speed_travel", "travel_speed")),
        first_layer_speed_mm_s=_float(_value(data, "speed_layer_0", "first_layer_speed", "initial_layer_speed")),
        nozzle_temperature_c=_int(_value(data, "material_print_temperature", "temperature", "nozzle_temperature")), bed_temperature_c=_int(_value(data, "material_bed_temperature", "bed_temperature")),
        fan_speed_percent=_int(_value(data, "cool_fan_speed", "max_fan_speed", "fan_max_speed")),
        flow_percent=(flow * 100.0 if flow is not None and flow <= 2.0 else flow),
        extrusion_width_mm=_float(_value(data, "extrusion_width", "line_width")),
        retraction=RetractionSettings(_float(_value(data, "retraction_amount", "retract_length", "retraction_length")), _float(_value(data, "retraction_retract_speed", "retract_speed", "retraction_speed")), _float(_value(data, "retraction_hop", "retract_lift", "z_hop"))),
        adhesion=AdhesionSettings(_float(data.get("brim_width")), _int(_value(data, "skirts", "skirt_loops")), _int(data.get("raft_layers"))),
        ironing_enabled=_bool(data.get("ironing")) if "ironing" in data else (None if ironing is None else ironing != "no_ironing"),
        seam_position=_str(_value(data, "z_seam_type", "seam_position")), acceleration_mm_s2=_float(_value(data, "acceleration_print", "default_acceleration")),
        jerk_mm_s=_float(data.get("jerk_print")), variable_layer_height=_bool(data.get("variable_layer_height")),
        source_values=tuple(sorted((key, json.dumps(value, sort_keys=True)) for key, value in data.items() if key not in known)),
    )


def filament_resources(data: dict[str, object]) -> tuple[tuple[Material, ...], tuple[ToolAssignment, ...]]:
    colors = data.get("filament_colour", [])
    types = data.get("filament_type", [])
    names = data.get("filament_settings_id", [])
    diameters = data.get("filament_diameter", [])
    colors = colors if isinstance(colors, list) else [colors]
    types = types if isinstance(types, list) else [types]
    names = names if isinstance(names, list) else [names]
    diameters = diameters if isinstance(diameters, list) else [diameters]
    count = max(len(colors), len(types), len(names), len(diameters), 0)
    materials: list[Material] = []
    assignments: list[ToolAssignment] = []
    for index in range(count):
        material_id = f"filament-slot:{index + 1}"
        color = str(colors[index]).rstrip(";") if index < len(colors) and colors[index] else None
        filament_type = str(types[index]) if index < len(types) and types[index] else None
        name = str(names[index]) if index < len(names) and names[index] else (filament_type or material_id)
        diameter = _float(diameters[index]) if index < len(diameters) else None
        materials.append(Material(material_id, name=name, material_type="filament", filament_type=filament_type, color=color, diameter_mm=diameter))
        assignments.append(ToolAssignment(index, material_id, color, filament_type))
    return tuple(materials), tuple(assignments)
