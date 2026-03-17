"""
AutoSlice — In-place vertex rotation for 3MF model XML files.

rotate_model_xml(xml_bytes, rot_3x3)  →  bytes

Parses a .model XML file, applies a 3×3 rotation matrix to every vertex,
translates the mesh so Z_min = 0 (placed on the build plate), and returns
the modified XML as UTF-8 bytes.

No external dependencies — uses stdlib xml.etree.ElementTree + numpy.
Falls back to returning original bytes if anything fails (non-fatal).
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET

import numpy as np

# Known 3MF namespace URIs → register so ET re-serialises with clean prefixes
_NS_MAP = {
    "":  "http://schemas.microsoft.com/3dmanufacturing/core/2015/02",
    "p": "http://schemas.microsoft.com/3dmanufacturing/material/2015/02",
    "b": "http://schemas.bambulab.com/package/2021",
    "BambuStudio": "http://schemas.bambulab.com/package/2021",
}


def euler_deg_to_rotation_matrix(rx: float, ry: float, rz: float) -> np.ndarray:
    """
    Build a 3×3 rotation matrix from Euler angles in degrees.
    Application order: Rz @ Ry @ Rx  (extrinsic X→Y→Z).
    For the axis-aligned candidates used by the orientation scorer, only
    one angle is non-zero, so the order doesn't matter in practice.
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

    rx_r = math.radians(rx)
    ry_r = math.radians(ry)
    rz_r = math.radians(rz)
    return _rz(rz_r) @ _ry(ry_r) @ _rx(rx_r)


def rotate_model_xml(xml_bytes: bytes, rot_3x3: np.ndarray) -> bytes:
    """
    Apply rot_3x3 to every <vertex x y z> in the XML, translate so Z_min=0,
    and return the modified file as UTF-8 bytes.

    Returns original bytes unchanged on any error.
    """
    try:
        return _rotate(xml_bytes, rot_3x3)
    except Exception:
        return xml_bytes


def _rotate(xml_bytes: bytes, rot_3x3: np.ndarray) -> bytes:
    # Register namespaces before parsing so ET preserves them on output
    for prefix, uri in _NS_MAP.items():
        ET.register_namespace(prefix, uri)

    root = ET.fromstring(xml_bytes)

    # Collect all <vertex> elements (namespace-agnostic)
    vertex_els: list[ET.Element] = []
    coords: list[list[float]] = []

    for el in root.iter():
        local = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        if local == "vertex":
            try:
                coords.append([
                    float(el.attrib["x"]),
                    float(el.attrib["y"]),
                    float(el.attrib["z"]),
                ])
                vertex_els.append(el)
            except (KeyError, ValueError):
                continue

    if not vertex_els:
        return xml_bytes

    verts = np.array(coords, dtype=np.float64)   # (N, 3)
    rotated = (rot_3x3 @ verts.T).T               # (N, 3)

    # Translate so the lowest point sits on Z=0
    z_min = float(rotated[:, 2].min())
    rotated[:, 2] -= z_min

    # Write rotated coordinates back into the elements
    for el, (x, y, z) in zip(vertex_els, rotated):
        el.attrib["x"] = f"{x:.6f}"
        el.attrib["y"] = f"{y:.6f}"
        el.attrib["z"] = f"{z:.6f}"

    # Serialise — ET preserves namespace declarations registered above
    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return xml_str.encode("utf-8")
