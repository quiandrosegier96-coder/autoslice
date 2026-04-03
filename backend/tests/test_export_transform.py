"""
Tests for AutoSlice export pipeline:
  - G-code extrusion mode safety (absolute vs relative)
  - 3MF item-transform normalization
  - 3MF item-transform rotation
"""

import json
import textwrap
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from app.export.mesh_transform import (
    euler_deg_to_rotation_matrix,
    normalize_model_xml,
    rotate_model_xml,
    _parse_transform,
    _matrix_to_transform,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_model_xml(objects: list[dict], items: list[dict]) -> bytes:
    """
    Build a minimal 3MF model XML for testing.

    objects: [{"id": "1", "vertices": [(x,y,z), ...], "triangles": [(v1,v2,v3), ...]}]
    items:   [{"objectid": "1", "transform": "..."}]  (transform optional)
    """
    NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    ET.register_namespace("", NS)
    root = ET.Element(f"{{{NS}}}model")
    root.set("unit", "millimeter")
    resources = ET.SubElement(root, f"{{{NS}}}resources")
    build     = ET.SubElement(root, f"{{{NS}}}build")

    for obj in objects:
        obj_el = ET.SubElement(resources, f"{{{NS}}}object")
        obj_el.set("id", obj["id"])
        obj_el.set("type", "model")
        mesh   = ET.SubElement(obj_el, f"{{{NS}}}mesh")
        verts  = ET.SubElement(mesh,   f"{{{NS}}}vertices")
        tris   = ET.SubElement(mesh,   f"{{{NS}}}triangles")
        for x, y, z in obj["vertices"]:
            v = ET.SubElement(verts, f"{{{NS}}}vertex")
            v.set("x", str(x)); v.set("y", str(y)); v.set("z", str(z))
        for v1, v2, v3 in obj.get("triangles", []):
            t = ET.SubElement(tris, f"{{{NS}}}triangle")
            t.set("v1", str(v1)); t.set("v2", str(v2)); t.set("v3", str(v3))

    for item in items:
        item_el = ET.SubElement(build, f"{{{NS}}}item")
        item_el.set("objectid", item["objectid"])
        if "transform" in item:
            item_el.set("transform", item["transform"])

    return ET.tostring(root, encoding="unicode", xml_declaration=False).encode("utf-8")


def _get_vertices(xml_bytes: bytes) -> list[tuple[float, float, float]]:
    root = ET.fromstring(xml_bytes)
    verts = []
    for el in root.iter():
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        if tag == "vertex":
            verts.append((float(el.attrib["x"]),
                           float(el.attrib["y"]),
                           float(el.attrib["z"])))
    return verts


def _get_item_transforms(xml_bytes: bytes) -> list[str]:
    root = ET.fromstring(xml_bytes)
    transforms = []
    for el in root.iter():
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        if tag == "item":
            transforms.append(el.attrib.get("transform", ""))
    return transforms


def _is_identity_transform(t: str) -> bool:
    if not t:
        return True
    m = _parse_transform(t)
    return bool(np.allclose(m, np.eye(4), atol=1e-3))


# ── Test 1: absolute extrusion mode — process config ─────────────────────────

def test_absolute_extrusion_mode_no_per_layer_reset():
    """
    Absolute extrusion mode must NOT set layer_change_gcode to G92 E0.
    Inserting G92 E0 per-layer in absolute mode resets the E counter while the
    slicer continues emitting cumulative E values — causing over-extrusion.
    """
    import dataclasses
    from app.export.xml_builder import _make_process_config
    from app.models.print_settings import PrintSettings

    # Build minimal settings
    s = PrintSettings(
        layer_height_mm=0.2,
        first_layer_height_mm=0.25,
        wall_count=3,
        top_layers=4,
        bottom_layers=4,
        infill_percent=15,
        infill_pattern="gyroid",
        supports_enabled=False,
        support_type="normal",
        support_density_percent=15,
        support_angle_threshold_deg=50,
        brim_enabled=False,
        brim_width_mm=5.0,
        skirt_loops=1,
        nozzle_temp_c=220,
        bed_temp_c=60,
        print_speed_mm_s=200,
        first_layer_speed_mm_s=30,
        fan_speed_percent=100,
        fan_first_layer=False,
    )

    cfg = _make_process_config(s)

    # Must be absolute mode
    assert cfg.get("use_relative_e_distances") == "0", \
        "Expected absolute extrusion (use_relative_e_distances=0)"

    # Must NOT have G92 E0 as layer change gcode in absolute mode
    layer_gcode = cfg.get("layer_change_gcode", "")
    assert "G92 E0" not in layer_gcode or layer_gcode == "", (
        f"layer_change_gcode contains G92 E0 which is unsafe in absolute "
        f"extrusion mode: '{layer_gcode}'"
    )


# ── Test 2: transform parsing round-trip ─────────────────────────────────────

def test_parse_transform_roundtrip():
    """_parse_transform and _matrix_to_transform must be inverses."""
    original = "1.0 0.0 0.0  0.0 1.0 0.0  0.0 0.0 1.0  10.5 -3.2 7.8"
    mat = _parse_transform(original)
    roundtripped = _parse_transform(_matrix_to_transform(mat))
    assert np.allclose(mat, roundtripped, atol=1e-5)


def test_parse_transform_translation():
    """Translation components must land in column 3 (right column) of the matrix."""
    t = "1 0 0  0 1 0  0 0 1  10 20 30"
    m = _parse_transform(t)
    assert np.allclose(m[:3, 3], [10, 20, 30], atol=1e-5)
    assert np.allclose(m[:3, :3], np.eye(3), atol=1e-5)


# ── Test 3: normalize_model_xml — single item with translate ─────────────────

def test_normalize_bakes_translation():
    """
    normalize_model_xml must apply a pure-translation item transform to vertices
    and reset the item transform to identity.
    """
    # Object: unit cube at origin
    verts = [(0,0,0),(1,0,0),(0,1,0),(0,0,1)]
    # Item: translate by (50, 0, 0)
    tx = "1 0 0  0 1 0  0 0 1  50 0 0"
    xml_in = _make_model_xml(
        objects=[{"id": "1", "vertices": verts, "triangles": [(0,1,2),(0,2,3)]}],
        items=[{"objectid": "1", "transform": tx}],
    )

    xml_out = normalize_model_xml(xml_in)
    out_verts = _get_vertices(xml_out)
    transforms = _get_item_transforms(xml_out)

    # Vertices must be shifted by +50 in X
    xs = [v[0] for v in out_verts]
    assert min(xs) >= 49.9, f"Expected vertices shifted to x≥50, got {min(xs)}"

    # Item transform must be identity
    assert _is_identity_transform(transforms[0]), \
        f"Expected identity transform after baking, got '{transforms[0]}'"


def test_normalize_preserves_relative_placement():
    """
    normalize_model_xml with two independent items must preserve their relative
    world-space positions after baking.
    """
    # Two objects, both unit cubes at origin
    obj_a = {"id": "1", "vertices": [(0,0,0),(1,0,0),(0,1,0),(0,0,1)],
             "triangles": [(0,1,2)]}
    obj_b = {"id": "2", "vertices": [(0,0,0),(1,0,0),(0,1,0),(0,0,1)],
             "triangles": [(0,1,2)]}

    # Item A: at x=0, item B: at x=100
    tx_a = "1 0 0  0 1 0  0 0 1  0 0 0"
    tx_b = "1 0 0  0 1 0  0 0 1  100 0 0"

    xml_in = _make_model_xml(
        objects=[obj_a, obj_b],
        items=[
            {"objectid": "1", "transform": tx_a},
            {"objectid": "2", "transform": tx_b},
        ],
    )

    xml_out = normalize_model_xml(xml_in)

    # Parse vertex positions per object from the output
    root = ET.fromstring(xml_out)
    all_verts = []
    for el in root.iter():
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        if tag == "vertex":
            all_verts.append(float(el.attrib["x"]))

    xs = sorted(all_verts)
    # Object A stays near x=0, object B stays near x=100
    # The relative separation of ~100 must be preserved
    assert max(xs) - min(xs) >= 99, \
        f"Assembly separation not preserved: xs range = {min(xs):.1f}..{max(xs):.1f}"


def test_normalize_skips_instanced_objects():
    """
    When two items reference the same object (instancing), normalize_model_xml
    must NOT bake either transform — doing so would corrupt geometry for the
    second instance.
    """
    verts = [(0,0,0),(1,0,0),(0,1,0)]
    tx_a = "1 0 0  0 1 0  0 0 1  10 0 0"
    tx_b = "1 0 0  0 1 0  0 0 1  50 0 0"

    xml_in = _make_model_xml(
        objects=[{"id": "1", "vertices": verts, "triangles": [(0,1,2)]}],
        items=[
            {"objectid": "1", "transform": tx_a},
            {"objectid": "1", "transform": tx_b},
        ],
    )

    xml_out = normalize_model_xml(xml_in)

    # Output should equal input — instanced objects must not be baked
    out_verts = _get_vertices(xml_out)
    in_verts  = _get_vertices(xml_in)
    for ov, iv in zip(out_verts, in_verts):
        assert np.allclose(ov, iv, atol=1e-4), \
            f"Instanced vertices were modified: {iv} → {ov}"


# ── Test 4: rotate_model_xml — no double-transform ───────────────────────────

def test_rotate_no_double_transform():
    """
    rotate_model_xml must not double-apply transformation:
    if an item has a transform, rotation must yield the same result as
    manually computing rot @ (R_old @ v + T_old) for every vertex.
    """
    # Object: triangle
    verts = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]

    # Item has a 90° Y rotation and a translation in its existing transform
    # 90° Y rotation: [[0,0,1],[0,1,0],[-1,0,0]] (column-major in 3MF)
    # In 3MF column-major: col0=(0,0,-1), col1=(0,1,0), col2=(1,0,0), trans=(5,0,0)
    tx = "0 0 -1  0 1 0  1 0 0  5 0 0"

    xml_in = _make_model_xml(
        objects=[{"id": "1", "vertices": verts, "triangles": [(0,1,2)]}],
        items=[{"objectid": "1", "transform": tx}],
    )

    # Apply 90° Z rotation
    rot = euler_deg_to_rotation_matrix(0, 0, 90)
    xml_out = rotate_model_xml(xml_in, rot)

    out_verts = np.array(_get_vertices(xml_out))

    # Manually compute expected world positions
    R_old = _parse_transform(tx)[:3, :3]
    T_old = _parse_transform(tx)[:3, 3]
    expected_world = np.array([(rot @ (R_old @ np.array(v) + T_old))
                                for v in verts])
    # Z-seat: shift so min Z = 0
    expected_world[:, 2] -= expected_world[:, 2].min()

    assert np.allclose(out_verts, expected_world, atol=1e-3), (
        f"Double-transform detected.\n"
        f"Expected:\n{expected_world}\nGot:\n{out_verts}"
    )


def test_rotate_item_transforms_reset_to_identity():
    """After rotate_model_xml, all item transforms must be identity."""
    verts = [(0,0,0),(1,0,0),(0,0,1)]
    tx = "1 0 0  0 1 0  0 0 1  20 0 0"
    xml_in = _make_model_xml(
        objects=[{"id": "1", "vertices": verts, "triangles": [(0,1,2)]}],
        items=[{"objectid": "1", "transform": tx}],
    )

    rot = euler_deg_to_rotation_matrix(-90, 0, 0)
    xml_out = rotate_model_xml(xml_in, rot)
    for t in _get_item_transforms(xml_out):
        assert _is_identity_transform(t), \
            f"Item transform not reset to identity: '{t}'"


def test_rotate_zseats_assembly():
    """After rotate_model_xml the minimum Z coordinate must be ≥ 0."""
    verts = [(0,0,5),(1,0,5),(0,1,5),(0,0,6)]
    xml_in = _make_model_xml(
        objects=[{"id": "1", "vertices": verts, "triangles": [(0,1,2),(0,2,3)]}],
        items=[{"objectid": "1"}],
    )

    rot = euler_deg_to_rotation_matrix(180, 0, 0)   # flip upside down
    xml_out = rotate_model_xml(xml_in, rot)
    zs = [v[2] for v in _get_vertices(xml_out)]
    assert min(zs) >= -0.001, f"Assembly not Z-seated: min Z = {min(zs):.4f}"


# ── Test 5: process config — extrusion mode consistency ──────────────────────

def test_no_m83_in_absolute_mode():
    """
    With use_relative_e_distances=0 (absolute), the config must not emit M83
    (relative extrusion) anywhere in start/layer gcode fields.
    """
    import dataclasses
    from app.export.xml_builder import _make_process_config
    from app.models.print_settings import PrintSettings

    s = PrintSettings(
        layer_height_mm=0.2, first_layer_height_mm=0.25,
        wall_count=3, top_layers=4, bottom_layers=4,
        infill_percent=15, infill_pattern="gyroid",
        supports_enabled=False, support_type="normal",
        support_density_percent=15, support_angle_threshold_deg=50,
        brim_enabled=False, brim_width_mm=5.0, skirt_loops=1,
        nozzle_temp_c=220, bed_temp_c=60,
        print_speed_mm_s=200, first_layer_speed_mm_s=30,
        fan_speed_percent=100, fan_first_layer=False,
    )

    cfg = _make_process_config(s)
    assert cfg.get("use_relative_e_distances") == "0"

    # Check no gcode field emits M83
    gcode_fields = ["machine_start_gcode", "layer_change_gcode",
                    "machine_end_gcode", "before_layer_change_gcode"]
    for field in gcode_fields:
        gcode = cfg.get(field, "")
        assert "M83" not in gcode, \
            f"M83 found in '{field}' despite absolute extrusion mode: '{gcode}'"
