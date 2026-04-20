"""
AutoSlice — In-place vertex rotation and transform normalization for 3MF model XML.

Public API:
  rotate_model_xml(xml_bytes, rot_3x3)  →  bytes
  normalize_model_xml(xml_bytes)        →  bytes

Both functions fall back to returning original bytes on any error (non-fatal).
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections import Counter

import numpy as np

# Known 3MF namespace URIs → register so ET re-serialises with clean prefixes
_NS_MAP = {
    "":           "http://schemas.microsoft.com/3dmanufacturing/core/2015/02",
    "p":          "http://schemas.microsoft.com/3dmanufacturing/material/2015/02",
    "b":          "http://schemas.bambulab.com/package/2021",
    "BambuStudio": "http://schemas.bambulab.com/package/2021",
}


# ── Public helpers ────────────────────────────────────────────────────────────

def euler_deg_to_rotation_matrix(rx: float, ry: float, rz: float) -> np.ndarray:
    """
    Build a 3×3 rotation matrix from Euler angles in degrees.
    Application order: Rz @ Ry @ Rx  (extrinsic X→Y→Z).
    """
    def _rx(a: float) -> np.ndarray:
        c, s = math.cos(a), math.sin(a)
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float64)

    def _ry(a: float) -> np.ndarray:
        c, s = math.cos(a), math.sin(a)
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float64)

    def _rz(a: float) -> np.ndarray:
        c, s = math.cos(a), math.sin(a)
        return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)

    return _rz(math.radians(rz)) @ _ry(math.radians(ry)) @ _rx(math.radians(rx))


def rotate_model_xml(xml_bytes: bytes, rot_3x3: np.ndarray) -> bytes:
    """
    Apply rot_3x3 to a 3MF model XML:
      1. Bake all <item transform> into vertex coordinates (world space)
      2. Rotate all vertices by rot_3x3
      3. Z-seat the assembly (min Z → 0)
      4. Reset all item transforms to identity

    Returns original bytes unchanged on any error.
    """
    try:
        return _rotate(xml_bytes, rot_3x3)
    except Exception:
        return xml_bytes


def scale_model_xml(xml_bytes: bytes, scale: float) -> bytes:
    """
    Uniformly scale all vertex coordinates in a 3MF model XML by `scale`.
    Returns original bytes unchanged on any error or when scale ≈ 1.
    """
    if abs(scale - 1.0) <= 0.001:
        return xml_bytes
    try:
        return _scale(xml_bytes, scale)
    except Exception:
        return xml_bytes


def normalize_model_xml(xml_bytes: bytes) -> bytes:
    """
    Normalize a 3MF model XML without rotating it.

    Bakes each <item transform> into the referenced object's vertex coordinates
    so Anycubic Slicer sees correctly assembled world-space geometry regardless
    of whether it honours the transform attribute.

    Safety: objects referenced by more than one <item> (instanced objects) are
    left untouched — their transform attribute is preserved as-is so the slicer
    can still place the instances correctly.

    Returns original bytes unchanged on any error.
    """
    try:
        return _normalize(xml_bytes)
    except Exception:
        return xml_bytes


# ── Internal: 3MF transform parsing ──────────────────────────────────────────

def _local_tag(el: ET.Element) -> str:
    tag = el.tag
    return tag.split("}")[-1] if "}" in tag else tag


def _parse_transform(s: str) -> np.ndarray:
    """
    Parse a 3MF transform attribute (12 floats, column-major 4×3) into a 4×4
    homogeneous matrix.

    3MF column-major layout:
      m00 m01 m02  m10 m11 m12  m20 m21 m22  tx ty tz
    where the columns are the X, Y, Z basis vectors of the local frame.
    """
    vals = [float(v) for v in s.split()]
    if len(vals) != 12:
        return np.eye(4, dtype=np.float64)
    m = np.eye(4, dtype=np.float64)
    m[0, 0], m[1, 0], m[2, 0] = vals[0],  vals[1],  vals[2]   # col 0
    m[0, 1], m[1, 1], m[2, 1] = vals[3],  vals[4],  vals[5]   # col 1
    m[0, 2], m[1, 2], m[2, 2] = vals[6],  vals[7],  vals[8]   # col 2
    m[0, 3], m[1, 3], m[2, 3] = vals[9],  vals[10], vals[11]  # translation
    return m


def _matrix_to_transform(m: np.ndarray) -> str:
    """Serialise a 4×4 matrix back to a 3MF transform string (12 floats)."""
    return " ".join([
        f"{m[0,0]:.6f}", f"{m[1,0]:.6f}", f"{m[2,0]:.6f}",
        f"{m[0,1]:.6f}", f"{m[1,1]:.6f}", f"{m[2,1]:.6f}",
        f"{m[0,2]:.6f}", f"{m[1,2]:.6f}", f"{m[2,2]:.6f}",
        f"{m[0,3]:.6f}", f"{m[1,3]:.6f}", f"{m[2,3]:.6f}",
    ])


def _identity_transform() -> str:
    return _matrix_to_transform(np.eye(4, dtype=np.float64))


# ── Internal: vertex helpers ──────────────────────────────────────────────────

def _collect_vertices(
    obj_el: ET.Element,
) -> tuple[list[ET.Element], np.ndarray]:
    """Return all <vertex> elements and their coordinates as an (N,3) array."""
    els: list[ET.Element] = []
    coords: list[list[float]] = []
    for el in obj_el.iter():
        if _local_tag(el) == "vertex":
            try:
                coords.append([float(el.attrib["x"]),
                                float(el.attrib["y"]),
                                float(el.attrib["z"])])
                els.append(el)
            except (KeyError, ValueError):
                pass
    if not els:
        return els, np.empty((0, 3), dtype=np.float64)
    return els, np.array(coords, dtype=np.float64)


def _write_vertices(els: list[ET.Element], verts: np.ndarray) -> None:
    for el, (x, y, z) in zip(els, verts):
        el.attrib["x"] = f"{x:.6f}"
        el.attrib["y"] = f"{y:.6f}"
        el.attrib["z"] = f"{z:.6f}"


# ── Internal: bake item transforms into vertex coordinates ────────────────────

def _bake_item_transforms(
    root: ET.Element,
    obj_map: dict[str, ET.Element],
    skip_multi_ref: bool = True,
) -> bool:
    """
    For each <item> that has a non-identity transform, apply the transform to
    the referenced object's vertices and reset the item transform to identity.

    skip_multi_ref: if True (default), objects referenced by >1 item are skipped
    to avoid corrupting instanced geometry.

    Returns True if any vertices were modified.
    """
    # Count how many items reference each objectid
    ref_counts: Counter[str] = Counter()
    for el in root.iter():
        if _local_tag(el) == "item":
            oid = el.attrib.get("objectid", "")
            if oid:
                ref_counts[oid] += 1

    changed = False
    for el in root.iter():
        if _local_tag(el) != "item":
            continue
        transform_str = el.attrib.get("transform", "")
        obj_id        = el.attrib.get("objectid", "")
        if not transform_str or not obj_id or obj_id not in obj_map:
            continue
        if skip_multi_ref and ref_counts[obj_id] > 1:
            # Instanced object — leave the transform in place
            continue

        mat = _parse_transform(transform_str)
        # Skip identity transforms (within floating-point tolerance)
        if np.allclose(mat, np.eye(4), atol=1e-4):
            continue

        rot   = mat[:3, :3]
        trans = mat[:3, 3]

        v_els, verts = _collect_vertices(obj_map[obj_id])
        if not v_els:
            continue

        # World position = R @ local_pos + T
        verts_world = (rot @ verts.T).T + trans
        _write_vertices(v_els, verts_world)
        el.attrib["transform"] = _identity_transform()
        changed = True

    return changed


# ── _normalize (no rotation) ──────────────────────────────────────────────────

def _normalize(xml_bytes: bytes) -> bytes:
    for prefix, uri in _NS_MAP.items():
        ET.register_namespace(prefix, uri)

    root = ET.fromstring(xml_bytes)

    obj_map: dict[str, ET.Element] = {}
    for el in root.iter():
        if _local_tag(el) == "object":
            oid = el.attrib.get("id", "")
            if oid:
                obj_map[oid] = el

    changed = _bake_item_transforms(root, obj_map, skip_multi_ref=True)

    if not changed:
        return xml_bytes

    return ET.tostring(root, encoding="unicode", xml_declaration=False).encode("utf-8")


# ── _rotate (with rotation) ───────────────────────────────────────────────────

def _rotate(xml_bytes: bytes, rot_3x3: np.ndarray) -> bytes:
    for prefix, uri in _NS_MAP.items():
        ET.register_namespace(prefix, uri)

    root = ET.fromstring(xml_bytes)

    # Build object map
    obj_map: dict[str, ET.Element] = {}
    for el in root.iter():
        if _local_tag(el) == "object":
            oid = el.attrib.get("id", "")
            if oid:
                obj_map[oid] = el

    # ── Step 1: bake all item transforms into vertex coordinates ─────────────
    # This brings every vertex into world space before we apply the new rotation.
    # Correct because: rot_new @ (R_old @ v + T_old) requires v to already be
    # in world space.  Skipping this step would lose the R_old component when
    # items carry a rotational transform (e.g. Bambu component placements).
    _bake_item_transforms(root, obj_map, skip_multi_ref=False)

    # ── Step 2: collect all vertices (now in world space) ────────────────────
    all_v_els: list[ET.Element] = []
    all_coords: list[list[float]] = []
    for el in root.iter():
        if _local_tag(el) == "vertex":
            try:
                all_coords.append([float(el.attrib["x"]),
                                    float(el.attrib["y"]),
                                    float(el.attrib["z"])])
                all_v_els.append(el)
            except (KeyError, ValueError):
                pass

    if not all_v_els:
        return xml_bytes

    verts = np.array(all_coords, dtype=np.float64)   # (N, 3)

    # ── Step 3: apply rotation ───────────────────────────────────────────────
    rotated = (rot_3x3 @ verts.T).T                   # (N, 3)

    # ── Step 4: Z-seat — translate so min Z = 0 ─────────────────────────────
    z_min = float(rotated[:, 2].min())
    rotated[:, 2] -= z_min

    _write_vertices(all_v_els, rotated)

    # ── Step 5: reset all item transforms to identity ────────────────────────
    # Vertices are now in final world space; no additional transform needed.
    for el in root.iter():
        if _local_tag(el) == "item":
            el.attrib["transform"] = _identity_transform()

    return ET.tostring(root, encoding="unicode", xml_declaration=False).encode("utf-8")


# ── _scale ────────────────────────────────────────────────────────────────────

def _scale(xml_bytes: bytes, factor: float) -> bytes:
    for prefix, uri in _NS_MAP.items():
        ET.register_namespace(prefix, uri)

    root = ET.fromstring(xml_bytes)
    for el in root.iter():
        if _local_tag(el) == "vertex":
            try:
                el.attrib["x"] = f"{float(el.attrib['x']) * factor:.6f}"
                el.attrib["y"] = f"{float(el.attrib['y']) * factor:.6f}"
                el.attrib["z"] = f"{float(el.attrib['z']) * factor:.6f}"
            except (KeyError, ValueError):
                pass

    # Scale translation components of any item transforms
    for el in root.iter():
        if _local_tag(el) == "item":
            t = el.attrib.get("transform", "")
            if t:
                mat = _parse_transform(t)
                mat[0, 3] *= factor
                mat[1, 3] *= factor
                mat[2, 3] *= factor
                el.attrib["transform"] = _matrix_to_transform(mat)

    return ET.tostring(root, encoding="unicode", xml_declaration=False).encode("utf-8")
