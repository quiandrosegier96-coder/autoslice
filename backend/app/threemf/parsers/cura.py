"""Fixture-gated Ultimaker Cura adapter over secure core 3MF parsing."""

from dataclasses import replace
import json

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.container.xml import local_name, parse_xml
from app.threemf.detection.detector import DetectionResult, detect_3mf
from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.geometry import ObjectRole, ObjectSettings
from app.threemf.domain.materials import Material, ToolAssignment
from app.threemf.domain.metadata import SlicerType
from app.threemf.parsers.base import ThreeMFParser
from app.threemf.parsers.core import CoreThreeMFParser
from app.threemf.parsers.project_settings import settings_from_project

CURA_METADATA_PATHS = ("Metadata/cura.xml", "Metadata/Cura.config")


class CuraParser(ThreeMFParser):
    """Map only explicit Cura metadata; unknown package parts remain source-only opaque."""

    def __init__(self, core: CoreThreeMFParser | None = None) -> None:
        self._core = core or CoreThreeMFParser()

    def can_parse(self, container: ThreeMFContainer) -> DetectionResult:
        detected = detect_3mf(container)
        return detected if detected.slicer is SlicerType.CURA else DetectionResult(SlicerType.CURA, 0.0)

    def parse(self, container: ThreeMFContainer) -> Universal3MFDocument:
        detection = self.can_parse(container)
        if detection.confidence <= 0:
            raise ValueError("CuraParser requires multiple explicit Cura detection signals.")
        document = self._core.parse(container)
        global_values, object_values = _read_cura_metadata(container)
        tools = sorted({_tool_index(values.get("extruder_nr")) for values in object_values.values()} - {None})
        materials = tuple(Material(f"cura-extruder:{tool}", name=f"Cura extruder {tool + 1}", material_type="filament") for tool in tools)
        assignments = tuple(ToolAssignment(tool, f"cura-extruder:{tool}", metadata=(("source", "cura"),)) for tool in tools)
        objects = []
        for obj in document.objects:
            values = object_values.get(obj.object_id, {})
            tool = _tool_index(values.get("extruder_nr"))
            role = _role(values)
            objects.append(replace(
                obj, role=role, object_type=role.value,
                material_resource_id=f"cura-extruder:{tool}" if tool is not None else obj.material_resource_id,
                material_index=None if tool is not None else obj.material_index,
                settings=ObjectSettings(tuple(sorted(values.items()))),
            ))
        support_enabled = _boolean(global_values.get("support_enable"))
        support = replace(document.supports, enabled=support_enabled, source_values=tuple(sorted(
            (key, value) for key, value in global_values.items() if key.startswith("support_")
        )))
        return replace(
            document,
            source=replace(document.source, slicer=SlicerType.CURA, confidence=detection.confidence,
                           detection_evidence=detection.evidence, version=detection.version),
            objects=tuple(objects), process=settings_from_project(global_values),
            materials=document.materials + tuple(material for material in materials if material.material_id not in {item.material_id for item in document.materials}),
            tool_assignments=assignments, supports=support,
        )


def _read_cura_metadata(container: ThreeMFContainer) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    global_values: dict[str, str] = {}
    object_values: dict[str, dict[str, str]] = {}
    for path in CURA_METADATA_PATHS:
        if not container.exists(path):
            continue
        payload = container.read(path)
        if not payload.lstrip().startswith(b"<"):
            value = json.loads(payload.decode("utf-8", errors="replace"))
            if isinstance(value, dict):
                global_values.update((str(key).removeprefix("cura:"), str(item)) for key, item in value.items())
            continue
        root = parse_xml(payload, path)

        def visit(element, object_id: str | None = None) -> None:
            if local_name(element.tag) in {"object", "item"}:
                object_id = element.attrib.get("id") or element.attrib.get("objectid") or object_id
            if local_name(element.tag) in {"metadata", "setting"}:
                key = element.attrib.get("key") or element.attrib.get("name")
                value = element.attrib.get("value", element.text or "")
                if key:
                    (object_values.setdefault(object_id, {}) if object_id else global_values)[key.removeprefix("cura:")] = value
            for child in element:
                visit(child, object_id)

        visit(root)
    return global_values, object_values


def _tool_index(value: str | None) -> int | None:
    try:
        parsed = int(value) if value is not None else None
        return parsed if parsed is not None and parsed >= 0 else None
    except ValueError:
        return None


def _boolean(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.lower() in {"1", "true", "yes"}


def _role(values: dict[str, str]) -> ObjectRole:
    mesh_type = values.get("mesh_type", "").lower()
    return {
        "anti_overhang_mesh": ObjectRole.SUPPORT_BLOCKER,
        "support_mesh": ObjectRole.SUPPORT_ENFORCER,
        "infill_mesh": ObjectRole.MODIFIER,
        "cutting_mesh": ObjectRole.NEGATIVE_VOLUME,
    }.get(mesh_type, ObjectRole.MODEL)
