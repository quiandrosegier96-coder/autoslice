"""
AutoSlice — 3MF model parser.
Parses 3D/3dmodel.model XML to extract mesh objects (vertices + triangles).

Handles real-world Bambu Studio / MakerWorld 3MF files which may:
  - Use extra namespace declarations alongside the standard 3MF namespace
  - Have objects with <components> instead of direct <mesh> data
  - Have inconsistent namespace prefixes

Strategy: namespace-agnostic parsing — match elements by local tag name only.
"""

from pathlib import Path
from dataclasses import dataclass, field
import xml.etree.ElementTree as ET


@dataclass
class RawMeshObject:
    object_id: str
    name: str
    vertices: list[tuple[float, float, float]]   # (x, y, z)
    triangles: list[tuple[int, int, int]]         # (v1, v2, v3) indices
    object_type: str = "model"                   # "model", "negative_volume", "modifier", etc.


@dataclass
class ParsedModel:
    objects: list[RawMeshObject] = field(default_factory=list)
    unit: str = "millimeter"


# ---------------------------------------------------------------------------
# Namespace-agnostic helpers
# ---------------------------------------------------------------------------

def _tag(element: ET.Element) -> str:
    """Return the local tag name, stripping any namespace."""
    tag = element.tag
    return tag.split("}")[-1] if "}" in tag else tag


def _find(parent: ET.Element, local_name: str) -> ET.Element | None:
    for child in parent:
        if _tag(child) == local_name:
            return child
    return None


def _findall(parent: ET.Element, local_name: str) -> list[ET.Element]:
    return [child for child in parent if _tag(child) == local_name]


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_model_file(model_file: Path) -> ParsedModel:
    """
    Parse the 3D/3dmodel.model XML file from a Bambu/MakerWorld 3MF archive.

    Handles:
    - Standard 3MF: objects with direct <mesh> data
    - Bambu 3MF: objects with <components> referencing other mesh objects
    - Mixed assemblies: component objects pointing to mesh-bearing sub-objects
    """
    tree = ET.parse(model_file)
    root = tree.getroot()

    unit = root.attrib.get("unit", "millimeter")
    parsed = ParsedModel(unit=unit)

    resources = _find(root, "resources")
    if resources is None:
        return parsed

    all_objects = {obj.attrib.get("id", ""): obj for obj in _findall(resources, "object")}

    # First pass: collect objects that have direct mesh data
    mesh_objects: dict[str, RawMeshObject] = {}
    for obj_id, obj in all_objects.items():
        raw = _extract_mesh(obj, obj_id)
        if raw is not None:
            mesh_objects[obj_id] = raw

    if mesh_objects:
        # Return all mesh-bearing objects directly
        parsed.objects = list(mesh_objects.values())
        return parsed

    # Second pass: if no direct meshes found, follow <components> references.
    # Bambu assemblies reference mesh sub-objects via <components><component objectid="...">
    for obj_id, obj in all_objects.items():
        components_el = _find(obj, "components")
        if components_el is None:
            continue
        for comp in _findall(components_el, "component"):
            ref_id = comp.attrib.get("objectid", "")
            if ref_id in all_objects:
                raw = _extract_mesh(all_objects[ref_id], ref_id)
                if raw is not None and raw.object_id not in {r.object_id for r in parsed.objects}:
                    parsed.objects.append(raw)

    return parsed


def parse_model_files(
    model_files: list[Path],
    object_type_map: dict[str, str] | None = None,
) -> ParsedModel:
    """
    Parse all .model files from the archive and merge mesh objects found in any of them.
    This handles Bambu/Production-Extension 3MFs where geometry lives in Objects/ sub-files.

    object_type_map: optional {object_id: subtype} from Metadata/model_settings.config.
    When provided, each object's object_type is overridden with the Bambu subtype.
    """
    merged = ParsedModel()
    seen_ids: set[str] = set()
    errors: list[str] = []
    type_map = object_type_map or {}
    for f in model_files:
        try:
            result = parse_model_file(f)
            if merged.unit == "millimeter" and result.unit != "millimeter":
                merged.unit = result.unit
            for obj in result.objects:
                if obj.object_id not in seen_ids:
                    if obj.object_id in type_map:
                        obj.object_type = type_map[obj.object_id]
                    merged.objects.append(obj)
                    seen_ids.add(obj.object_id)
        except Exception as exc:
            errors.append(f"{f.name}: {exc}")
    if errors and not merged.objects:
        raise RuntimeError(f"All model files failed to parse: {errors}")
    return merged


def _extract_mesh(obj: ET.Element, fallback_id: str) -> RawMeshObject | None:
    """Extract vertex and triangle data from an <object> element, if present."""
    mesh_el = _find(obj, "mesh")
    if mesh_el is None:
        return None

    vertices_el = _find(mesh_el, "vertices")
    triangles_el = _find(mesh_el, "triangles")
    if vertices_el is None or triangles_el is None:
        return None

    vertices: list[tuple[float, float, float]] = []
    for v in _findall(vertices_el, "vertex"):
        try:
            vertices.append((float(v.attrib["x"]), float(v.attrib["y"]), float(v.attrib["z"])))
        except (KeyError, ValueError):
            continue

    triangles: list[tuple[int, int, int]] = []
    for t in _findall(triangles_el, "triangle"):
        try:
            triangles.append((int(t.attrib["v1"]), int(t.attrib["v2"]), int(t.attrib["v3"])))
        except (KeyError, ValueError):
            continue

    if not vertices or not triangles:
        return None

    obj_id = obj.attrib.get("id", fallback_id)
    name = obj.attrib.get("name", f"object_{obj_id}")
    return RawMeshObject(object_id=obj_id, name=name, vertices=vertices, triangles=triangles)
