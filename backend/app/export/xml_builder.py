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


def build_3mf_xml(parsed_model: ParsedModel, rotation_matrix=None) -> str:
    """
    Build a clean 3MF model XML with ALL printable objects merged into a single
    <object> so slicers never see unwanted part splits.

    If rotation_matrix (3×3 np.ndarray) is provided the vertices are rotated
    and the model is re-seated on the build plate (Z_min → 0).
    """
    import numpy as np

    ET.register_namespace("", _3MF_NS)
    root = ET.Element(f"{{{_3MF_NS}}}model")
    root.set("unit", "millimeter")
    root.set("xml:lang", "en-US")

    resources = ET.SubElement(root, f"{{{_3MF_NS}}}resources")
    build_el  = ET.SubElement(root, f"{{{_3MF_NS}}}build")

    # Collect printable objects
    printable = [o for o in parsed_model.objects if o.object_type not in _NON_PRINTABLE]
    if not printable:
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")

    # Merge vertices + triangles (adjust indices per object)
    all_verts: list[tuple[float, float, float]] = []
    all_tris:  list[tuple[int, int, int]]       = []
    offset = 0
    for obj in printable:
        all_verts.extend(obj.vertices)
        for t in obj.triangles:
            all_tris.append((t[0] + offset, t[1] + offset, t[2] + offset))
        offset += len(obj.vertices)

    # Apply rotation + re-seat on build plate
    if rotation_matrix is not None and all_verts:
        try:
            verts_arr = np.array(all_verts, dtype=np.float64)
            rotated   = (rotation_matrix @ verts_arr.T).T
            z_min     = float(rotated[:, 2].min())
            if abs(z_min) > 0.001:
                rotated[:, 2] -= z_min
            all_verts = [(float(v[0]), float(v[1]), float(v[2])) for v in rotated]
        except Exception:
            pass  # rotation failed — keep original verts

    # Single merged <object>
    name   = printable[0].name if len(printable) == 1 else "merged_model"
    obj_el = ET.SubElement(resources, f"{{{_3MF_NS}}}object")
    obj_el.set("id", "1")
    obj_el.set("name", name)
    obj_el.set("type", "model")

    mesh_el  = ET.SubElement(obj_el, f"{{{_3MF_NS}}}mesh")
    verts_el = ET.SubElement(mesh_el, f"{{{_3MF_NS}}}vertices")
    for x, y, z in all_verts:
        v = ET.SubElement(verts_el, f"{{{_3MF_NS}}}vertex")
        v.set("x", f"{x:.6f}")
        v.set("y", f"{y:.6f}")
        v.set("z", f"{z:.6f}")

    tris_el = ET.SubElement(mesh_el, f"{{{_3MF_NS}}}triangles")
    for v1, v2, v3 in all_tris:
        t = ET.SubElement(tris_el, f"{{{_3MF_NS}}}triangle")
        t.set("v1", str(v1))
        t.set("v2", str(v2))
        t.set("v3", str(v3))

    item = ET.SubElement(build_el, f"{{{_3MF_NS}}}item")
    item.set("objectid", "1")

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


# Maps AutoSlice build_plate values → Anycubic Slicer Next curr_bed_type string
# and the filament config temperature key that should carry the active bed temp.
# OrcaSlicer/Anycubic Slicer reads curr_bed_type from the process config and
# uses the matching plate temp key from the filament config.
_BED_TYPE_MAP: dict[str, tuple[str, str]] = {
    # (curr_bed_type value,  filament plate-temp key prefix)
    "smooth":        ("hot_plate",       "hot_plate_temp"),
    "textured":      ("textured_plate",  "textured_plate_temp"),
    "cold":          ("cool_plate",      "cool_plate_temp"),
    "high_temp":     ("eng_plate",       "eng_plate_temp"),
    "glass":         ("hot_plate",       "hot_plate_temp"),   # glass uses same slot as smooth
}
_BED_TYPE_DEFAULT = ("hot_plate", "hot_plate_temp")

_INFILL_MAP = {
    "gyroid": "gyroid",
    "grid": "grid",
    "honeycomb": "honeycomb",
    "lines": "line",
    "triangle": "triangles",
    "cubic": "cubic",
    "rectilinear": "rectilinear",
}

_SEAM_MAP = {
    "aligned": "aligned",
    "rear":    "back",    # OrcaSlicer uses "back", not "rear"
    "random":  "random",
    "nearest": "nearest",
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
    bridge_speed      = str(max(20, int(spd * 0.30)))   # 30% — unsupported bridges
    cfg = {
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
        "support_on_build_plate_only": "1" if settings.support_placement == "buildplate_only" else "0",
        "support_density": f"{settings.support_density_percent}%",
        "brim_type": brim_type,
        "brim_width": str(settings.brim_width_mm if settings.brim_enabled else 0),
        "skirt_loops": str(settings.skirt_loops),
        "skirt_distance": "2",
        "outer_wall_speed": outer_wall_speed,
        "inner_wall_speed": inner_wall_speed,
        "sparse_infill_speed": infill_speed,
        "internal_solid_infill_speed": solid_infill_speed,
        "top_surface_speed": top_surface_speed,
        "support_speed": support_speed,
        "initial_layer_speed": str(settings.first_layer_speed_mm_s),
        "initial_layer_infill_speed": str(settings.first_layer_speed_mm_s),
        "travel_speed": travel_speed,
        "line_width": str(settings.line_width_mm),
        "initial_layer_line_width": str(settings.first_layer_line_width_mm),
        "outer_wall_line_width": str(settings.line_width_mm),
        "inner_wall_line_width": str(settings.line_width_mm),
        "infill_line_width": str(settings.infill_line_width_mm),
        "top_surface_line_width": str(settings.line_width_mm),
        "support_line_width": str(settings.line_width_mm),
        # Bridge settings — slow + full fan + reduced flow for best bridging
        "bridge_speed": bridge_speed,
        "bridge_flow": "0.9",
        "enable_overhang_bridge_fan": "1",
        # Overhang wall detection — graduated slowdown as overhang increases
        "detect_overhang_wall": "1",
        "overhang_3_4_speed": str(max(15, int(spd * 0.30))),
        "overhang_4_4_speed": str(max(10, int(spd * 0.20))),
        # Wall generator — Arachne produces variable-width walls for better surface quality
        "wall_generator": "arachne",
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
        # Seam — map "rear" → "back" (OrcaSlicer spelling)
        "seam_position": _SEAM_MAP.get(settings.seam_position, settings.seam_position),
        # First layer quality
        "elefant_foot_compensation": "0.1",
        # Arc fitting — smoother curves in G-code, less file size
        "enable_arc_fitting": "1",
        # Retraction
        "retraction_length": [str(settings.retract_length_mm)],
        "retraction_speed": [str(settings.retract_speed_mm_s)],
        "z_hop": [str(settings.z_hop_mm)],
        "z_hop_types": ["Slope Lift"],
    }
    # Tree support extras
    if settings.support_type == "tree":
        cfg["support_style"] = "tree_slim"
        cfg["tree_support_branch_angle"] = "40"
        cfg["tree_support_wall_count"] = "1"

    # Bed type — tell Anycubic Slicer which plate is active
    curr_bed_type, _ = _BED_TYPE_MAP.get(settings.build_plate, _BED_TYPE_DEFAULT)
    cfg["curr_bed_type"] = curr_bed_type

    return cfg


def _make_filament_config(settings: PrintSettings, filament: FilamentType) -> dict:
    filament_display = _FILAMENT_TYPE_DISPLAY.get(filament.value, filament.value.upper())
    bed = str(settings.bed_temp_c)
    nozzle      = str(settings.nozzle_temp_c)
    nozzle_fl   = str(settings.first_layer_nozzle_temp_c or settings.nozzle_temp_c)

    # Determine which plate-temp key is active and set only that one to the real
    # bed temp. All other plate keys stay at "0" so Anycubic Slicer's automatic
    # plate-type detection doesn't get confused by stale values.
    _, active_plate_key = _BED_TYPE_MAP.get(settings.build_plate, _BED_TYPE_DEFAULT)
    _all_plate_keys = [
        "hot_plate_temp", "textured_plate_temp", "cool_plate_temp", "eng_plate_temp",
    ]
    plate_temps: dict[str, list[str]] = {}
    for key in _all_plate_keys:
        val = bed if key == active_plate_key else "0"
        plate_temps[key]                        = [val]
        plate_temps[f"{key}_initial_layer"]     = [val]

    return {
        "from": "project",
        "inherits": "",
        "filament_settings_id": [f"AutoSlice {filament_display}"],
        "filament_type": [filament_display],
        "filament_diameter": [str(settings.filament_diameter_mm)],
        "nozzle_temperature": [nozzle],
        "nozzle_temperature_initial_layer": [nozzle_fl],
        # Generic bed keys — used as fallback by some slicer versions
        "bed_temperature": [bed],
        "bed_temperature_initial_layer": [bed],
        # Plate-specific keys — only the active plate carries the real temp
        **plate_temps,
        "fan_max_speed": [str(settings.fan_speed_percent)],
        "fan_min_speed": [str(max(0, settings.fan_speed_percent - 20))],
        "close_fan_the_first_x_layers": ["0" if settings.fan_first_layer else "1"],
        "slow_down_layer_time": [str(settings.min_layer_time_s)],
        "pressure_advance": [str(settings.pressure_advance)],
        "enable_pressure_advance": ["1" if settings.pressure_advance > 0 else "0"],
        "wipe_before_change": ["1" if settings.wipe_on_retract else "0"],
        "coast_at_end_distance": [str(settings.coast_at_end_mm)],
    }


def _make_machine_config(settings: PrintSettings, printer: PrinterProfile, color_count: int = 1) -> dict:
    # Anycubic Slicer Next (OrcaSlicer) uses "<Display Name> <nozzle> nozzle" as the profile ID
    nozzle_str = str(settings.nozzle_size_mm).rstrip("0").rstrip(".")
    printer_settings_id = f"AutoSlice {nozzle_str}mm"
    cfg = {
        "from": "project",
        "inherits": "",
        "printer_settings_id": printer_settings_id,
        "nozzle_diameter": [str(settings.nozzle_size_mm)],
        "machine_max_speed_x": [str(printer.max_speed_mm_s)],
        "machine_max_speed_y": [str(printer.max_speed_mm_s)],
        "machine_max_speed_z": [str(printer.max_speed_z_mm_s)],
        "machine_max_acceleration_x": [str(printer.max_acceleration_xy)],
        "machine_max_acceleration_y": [str(printer.max_acceleration_xy)],
        "machine_max_acceleration_z": [str(printer.max_acceleration_z)],
        "machine_max_jerk_x": [str(printer.max_jerk)],
        "machine_max_jerk_y": [str(printer.max_jerk)],
        "machine_max_jerk_z": [str(printer.max_jerk)],
        "machine_max_jerk_e": [str(printer.max_jerk)],
        "min_layer_height": [str(printer.min_layer_height_mm)],
        "max_layer_height": [str(printer.max_layer_height_mm)],
        "printable_area": [
            "0x0",
            f"{printer.build_volume_x_mm}x0",
            f"{printer.build_volume_x_mm}x{printer.build_volume_y_mm}",
            f"0x{printer.build_volume_y_mm}",
        ],
        "printable_height": str(printer.build_volume_z_mm),
    }
    # ACE printers must always declare their full slot count regardless of how
    # many colors the user chose — Anycubic Slicer expects all slots to be defined.
    effective_colors = max(color_count, printer.max_colors if printer.max_colors > 1 else 1)
    if effective_colors > 1:
        cfg["single_extruder_multi_material"] = "1"
        cfg["single_extruder_multi_material_priming"] = "0"
        cfg["extruders_count"] = str(effective_colors)
    return cfg


_DEFAULT_COLORS = [
    "#FF0000", "#00AA00", "#0000FF", "#FF8800",
    "#AA00AA", "#00AAAA", "#FFFFFF", "#111111",
]

# Canonical per-filament temperatures used when per-slot type differs from the
# primary filament (important for multi-material prints mixing PLA + PETG etc.)
_SLOT_TEMPS: dict[str, dict] = {
    "pla":  {"nozzle": 200, "fl_nozzle": 220, "bed": 60},
    "petg": {"nozzle": 240, "fl_nozzle": 245, "bed": 80},
    "tpu":  {"nozzle": 230, "fl_nozzle": 235, "bed": 40},
}


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
    # ACE Pro / ACE Pro 2: always fill every hardware slot so Anycubic Slicer
    # never sees a slot count mismatch between machine config and filament configs.
    min_slots  = printer.max_colors if printer.max_colors > 1 else 1
    color_count = max(max(1, settings.color_count), min_slots)

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

        # Per-slot temperature override — critical when mixing filament types
        # (e.g. PLA in slot 1, PETG in slot 2 must have their own temps)
        temps = _SLOT_TEMPS.get(slot_filament.value, _SLOT_TEMPS["pla"])
        sl_nozzle    = str(temps["nozzle"])
        sl_nozzle_fl = str(temps["fl_nozzle"])
        sl_bed       = str(temps["bed"])
        _, active_plate_key = _BED_TYPE_MAP.get(settings.build_plate, _BED_TYPE_DEFAULT)
        fil["nozzle_temperature"]               = [sl_nozzle]
        fil["nozzle_temperature_initial_layer"] = [sl_nozzle_fl]
        fil["bed_temperature"]                  = [sl_bed]
        fil["bed_temperature_initial_layer"]    = [sl_bed]
        for _pk in ("hot_plate_temp", "textured_plate_temp", "cool_plate_temp", "eng_plate_temp"):
            _val = sl_bed if _pk == active_plate_key else "0"
            fil[_pk]                    = [_val]
            fil[f"{_pk}_initial_layer"] = [_val]

        filament_configs.append(fil)
        slot_colors.append(color)
        display = _FILAMENT_TYPE_DISPLAY.get(slot_filament.value, slot_filament.value.upper())
        slot_types_display.append(display)
        slot_types_id.append(f"AutoSlice {display}")
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

    # Multi-color: keep dedicated flush tower (do not route into infill/support)
    if color_count > 1:
        process["flush_into_infill"] = "0"
        process["flush_into_support"] = "0"
        process["flush_into_objects"] = "0"
        merged["flush_into_infill"] = "0"
        merged["flush_into_support"] = "0"
        merged["flush_into_objects"] = "0"

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
