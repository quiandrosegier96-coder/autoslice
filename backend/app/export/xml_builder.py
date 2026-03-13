"""
AutoSlice — 3MF XML builder and Anycubic config generator.
"""

import json
import xml.etree.ElementTree as ET

from app.models.print_settings import PrintSettings
from app.models.printer import PrinterProfile, FilamentType
from app.parser.model_parser import ParsedModel


_3MF_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"


def build_content_types_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        '  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
        '  <Default Extension="config" ContentType="application/xml"/>\n'
        '  <Default Extension="png" ContentType="image/png"/>\n'
        '</Types>'
    )


def build_rels_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Target="/3D/3dmodel.model" Id="rel0"'
        ' Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
        '</Relationships>'
    )


_NON_PRINTABLE = {"negative_volume", "modifier", "support_blocker", "support_enforcer"}


def build_3mf_xml(parsed_model: ParsedModel) -> str:
    ET.register_namespace("", _3MF_NS)
    root = ET.Element(f"{{{_3MF_NS}}}model")
    root.set("unit", parsed_model.unit)
    root.set("xml:lang", "en-US")

    resources = ET.SubElement(root, f"{{{_3MF_NS}}}resources")
    build_el = ET.SubElement(root, f"{{{_3MF_NS}}}build")

    for obj in parsed_model.objects:
        if obj.object_type in _NON_PRINTABLE:
            continue  # skip negative volumes, modifiers, support blockers/enforcers

        obj_id = obj.object_id if obj.object_id else "1"
        obj_el = ET.SubElement(resources, f"{{{_3MF_NS}}}object")
        obj_el.set("id", obj_id)
        obj_el.set("name", obj.name)
        obj_el.set("type", "model")

        mesh_el = ET.SubElement(obj_el, f"{{{_3MF_NS}}}mesh")

        verts_el = ET.SubElement(mesh_el, f"{{{_3MF_NS}}}vertices")
        for x, y, z in obj.vertices:
            v = ET.SubElement(verts_el, f"{{{_3MF_NS}}}vertex")
            v.set("x", f"{x:.6f}")
            v.set("y", f"{y:.6f}")
            v.set("z", f"{z:.6f}")

        tris_el = ET.SubElement(mesh_el, f"{{{_3MF_NS}}}triangles")
        for v1, v2, v3 in obj.triangles:
            t = ET.SubElement(tris_el, f"{{{_3MF_NS}}}triangle")
            t.set("v1", str(v1))
            t.set("v2", str(v2))
            t.set("v3", str(v3))

        item = ET.SubElement(build_el, f"{{{_3MF_NS}}}item")
        item.set("objectid", obj_id)

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


_INFILL_MAP = {
    "gyroid": "gyroid",
    "grid": "grid",
    "honeycomb": "honeycomb",
    "lines": "line",
    "triangle": "triangles",
    "cubic": "cubic",
    "rectilinear": "rectilinear",
}

_FILAMENT_TYPE_DISPLAY = {
    "pla": "PLA",
    "petg": "PETG",
    "tpu": "TPU",
}


def _make_process_config(settings: PrintSettings) -> dict:
    support_enabled = "1" if settings.supports_enabled else "0"
    support_type = "tree(auto)" if settings.support_type == "tree" else "normal"
    brim_type = "outer_brim" if settings.brim_enabled else "no_brim"
    spd = settings.print_speed_mm_s
    travel_speed = str(min(spd * 2, 500))
    # Differentiated speeds: outer wall is quality-critical (slowest),
    # infill is hidden (fastest), top surface is most visible (very slow)
    outer_wall_speed  = str(max(20, int(spd * 0.50)))   # 50% — quality first
    inner_wall_speed  = str(max(25, int(spd * 0.80)))   # 80%
    infill_speed      = str(spd)                         # 100% — hidden, go fast
    solid_infill_speed= str(max(30, int(spd * 0.80)))   # 80% — top/bottom layers
    top_surface_speed = str(max(20, int(spd * 0.40)))   # 40% — most visible surface
    support_speed     = str(max(30, int(spd * 0.60)))   # 60% — support stability
    return {
        "from": "project",
        "inherits": "",
        "layer_height": str(settings.layer_height_mm),
        "initial_layer_print_height": str(settings.first_layer_height_mm),
        "wall_loops": str(settings.wall_count),
        "top_shell_layers": str(settings.top_layers),
        "bottom_shell_layers": str(settings.bottom_layers),
        "sparse_infill_density": f"{settings.infill_percent}%",
        "sparse_infill_pattern": _INFILL_MAP.get(settings.infill_pattern, "grid"),
        "enable_support": support_enabled,
        "support_type": support_type,
        "support_threshold_angle": str(settings.support_angle_threshold_deg),
        "support_on_build_plate_only": "0",
        "brim_type": brim_type,
        "brim_width": str(settings.brim_width_mm if settings.brim_enabled else 0),
        "skirt_loops": str(settings.skirt_loops),
        "outer_wall_speed": outer_wall_speed,
        "inner_wall_speed": inner_wall_speed,
        "sparse_infill_speed": infill_speed,
        "internal_solid_infill_speed": solid_infill_speed,
        "top_surface_speed": top_surface_speed,
        "support_speed": support_speed,
        "initial_layer_speed": str(settings.first_layer_speed_mm_s),
        "initial_layer_infill_speed": str(settings.first_layer_speed_mm_s),
        "travel_speed": travel_speed,
        "line_width": str(settings.nozzle_size_mm),
        "initial_layer_line_width": str(round(settings.nozzle_size_mm * 1.25, 3)),
        "outer_wall_line_width": str(settings.nozzle_size_mm),
        "inner_wall_line_width": str(settings.nozzle_size_mm),
        "infill_line_width": str(round(settings.nozzle_size_mm * 1.1, 3)),
        "top_surface_line_width": str(settings.nozzle_size_mm),
        "support_line_width": str(settings.nozzle_size_mm),
        # Support gaps
        "support_top_z_distance": str(settings.support_top_z_distance_mm),
        "support_bottom_z_distance": str(settings.support_bottom_z_distance_mm),
        "support_object_xy_distance": str(settings.support_xy_distance_mm),
        # Support interface
        "support_interface_top_layers": str(settings.support_interface_layers) if settings.support_interface_enabled else "0",
        "support_interface_bottom_layers": str(settings.support_interface_layers) if settings.support_interface_enabled else "0",
        "support_interface_pattern": settings.support_interface_pattern if settings.support_interface_enabled else "concentric",
        "support_bottom_interface_spacing": "0.2",
        # Top surface quality
        "ironing_type": "top_surface" if settings.ironing_enabled else "no_ironing",
        "ironing_speed": str(max(15, settings.print_speed_mm_s // 5)),
        "top_surface_pattern": settings.top_surface_pattern,
        # Seam
        "seam_position": settings.seam_position,
        # Retraction
        "retraction_length": [str(settings.retract_length_mm)],
        "retraction_speed": [str(settings.retract_speed_mm_s)],
        "z_hop": [str(settings.z_hop_mm)],
        "z_hop_types": ["normal"],
    }


def _make_filament_config(settings: PrintSettings, filament: FilamentType) -> dict:
    filament_display = _FILAMENT_TYPE_DISPLAY.get(filament.value, filament.value.upper())
    bed = str(settings.bed_temp_c)
    # Set all plate temperature keys — Anycubic Slicer uses whichever matches the active plate
    return {
        "from": "project",
        "inherits": "",
        "filament_settings_id": [f"Generic {filament_display}"],
        "filament_type": [filament_display],
        "filament_diameter": [str(settings.filament_diameter_mm)],
        "nozzle_temperature": [str(settings.nozzle_temp_c)],
        "nozzle_temperature_initial_layer": [str(settings.nozzle_temp_c)],
        "hot_plate_temp": [bed],
        "hot_plate_temp_initial_layer": [bed],
        "textured_plate_temp": [bed],
        "textured_plate_temp_initial_layer": [bed],
        "cool_plate_temp": [bed],
        "cool_plate_temp_initial_layer": [bed],
        "eng_plate_temp": [bed],
        "eng_plate_temp_initial_layer": [bed],
        "fan_max_speed": [str(settings.fan_speed_percent)],
        "fan_min_speed": [str(max(0, settings.fan_speed_percent - 20))],
        "close_fan_the_first_x_layers": ["0" if settings.fan_first_layer else "1"],
        "slow_down_layer_time": [str(settings.min_layer_time_s)],
        "pressure_advance": [str(settings.pressure_advance)],
        "wipe_before_change": ["1" if settings.wipe_on_retract else "0"],
        "coast_at_end_distance": [str(settings.coast_at_end_mm)],
    }


def _make_machine_config(settings: PrintSettings, printer: PrinterProfile, color_count: int = 1) -> dict:
    # Anycubic Slicer Next (OrcaSlicer) uses "<Display Name> <nozzle> nozzle" as the profile ID
    nozzle_str = str(settings.nozzle_size_mm).rstrip("0").rstrip(".")
    printer_settings_id = f"{printer.display_name} {nozzle_str} nozzle"
    cfg = {
        "from": "project",
        "inherits": "",
        "printer_settings_id": printer_settings_id,
        "nozzle_diameter": [str(settings.nozzle_size_mm)],
        "machine_max_speed_x": [str(printer.max_speed_mm_s)],
        "machine_max_speed_y": [str(printer.max_speed_mm_s)],
        "printable_area": [
            "0x0",
            f"{printer.build_volume_x_mm}x0",
            f"{printer.build_volume_x_mm}x{printer.build_volume_y_mm}",
            f"0x{printer.build_volume_y_mm}",
        ],
        "printable_height": str(printer.build_volume_z_mm),
    }
    if color_count > 1:
        cfg["single_extruder_multi_material"] = "1"
        cfg["single_extruder_multi_material_priming"] = "0"
        cfg["extruders_count"] = str(color_count)
    return cfg


_DEFAULT_COLORS = [
    "#FF0000", "#00AA00", "#0000FF", "#FF8800",
    "#AA00AA", "#00AAAA", "#FFFFFF", "#111111",
]


def build_settings_configs(
    settings: PrintSettings,
    printer: PrinterProfile,
    filament: FilamentType,
) -> dict[str, str]:
    """
    Returns a dict of {zip_path: json_string} for the config files that
    Anycubic Slicer Next (OrcaSlicer-based) needs to fully restore print settings.

    For multi-color printers (ACE Pro / ACE Pro 2) a filament config is generated
    for each active color slot.
    """
    color_count = max(1, settings.color_count)
    process = _make_process_config(settings)
    machine = _make_machine_config(settings, printer, color_count)

    configs: dict[str, str] = {}

    filament_configs = []
    slot_colors = []
    slot_types_display = []
    slot_types_id = []

    for slot in range(color_count):
        slot_type_str = (
            settings.filament_types[slot]
            if settings.filament_types and slot < len(settings.filament_types)
            else filament.value
        )
        try:
            slot_filament = FilamentType(slot_type_str)
        except ValueError:
            slot_filament = filament

        color = (
            settings.filament_colors[slot]
            if settings.filament_colors and slot < len(settings.filament_colors)
            else _DEFAULT_COLORS[slot % len(_DEFAULT_COLORS)]
        )
        fil = _make_filament_config(settings, slot_filament)
        fil["filament_colour"] = [color]
        filament_configs.append(fil)
        slot_colors.append(color)
        display = _FILAMENT_TYPE_DISPLAY.get(slot_filament.value, slot_filament.value.upper())
        slot_types_display.append(display)
        slot_types_id.append(f"Generic {display}")
        configs[f"Metadata/filament_settings_{slot + 1}.config"] = json.dumps(fil, indent=2)

    merged: dict = {}
    merged.update(machine)
    merged.update(filament_configs[0])
    merged.update(process)
    # Always write arrays — Anycubic Slicer counts filament slots from these
    merged["filament_colour"] = slot_colors
    merged["filament_type"] = slot_types_display
    merged["filament_settings_id"] = slot_types_id
    merged["filament_diameter"] = [str(settings.filament_diameter_mm)] * color_count

    configs["Metadata/project_settings.config"] = json.dumps(merged, indent=2)
    configs["Metadata/process_settings_1.config"] = json.dumps(process, indent=2)
    configs["Metadata/machine_settings_1.config"] = json.dumps(machine, indent=2)
    return configs


# Keep old name as alias so nothing else breaks
def settings_to_project_config(
    settings: PrintSettings,
    printer: PrinterProfile,
    filament: FilamentType,
) -> str:
    return build_settings_configs(settings, printer, filament)["Metadata/project_settings.config"]
