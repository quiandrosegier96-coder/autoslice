"""Native Universal3MF to Anycubic project package exporter."""

from io import BytesIO
import json
import xml.etree.ElementTree as ET
import zipfile

from app.export.xml_builder import build_content_types_xml, build_rels_xml, build_settings_configs
from app.models.print_settings import PrintSettings as TargetPrintSettings
from app.models.printer import FilamentType, PrinterProfile
from app.threemf.domain.diagnostics import Severity, TranslationItem, TranslationReport, TranslationStatus
from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.metadata import SlicerType
from app.threemf.domain.resources import PreservationPolicy
from app.threemf.domain.settings import ConversionContext
from app.threemf.exporters.base import ExportResult, ThreeMFExporter
from app.threemf.validation import validate_3mf

CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"


class NativeAnycubicExporter(ThreeMFExporter):
    def __init__(self, settings: TargetPrintSettings, printer: PrinterProfile, filament: FilamentType) -> None:
        self._settings = settings
        self._printer = printer
        self._filament = filament

    def can_export(self, target: SlicerType) -> bool:
        return target is SlicerType.ANYCUBIC

    def export(self, document: Universal3MFDocument, context: ConversionContext) -> ExportResult:
        if context.target_slicer != SlicerType.ANYCUBIC.value:
            raise ValueError("NativeAnycubicExporter requires an Anycubic conversion context.")
        model_xml, object_ids, material_items = _build_model(document)
        configs = build_settings_configs(self._settings, self._printer, self._filament)
        model_settings = _build_explicit_model_settings(document, object_ids)
        output = BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr("[Content_Types].xml", build_content_types_xml())
            package.writestr("_rels/.rels", build_rels_xml())
            package.writestr("3D/3dmodel.model", model_xml)
            for path, payload in _safe_assets(document).items():
                package.writestr(path, payload)
            for path, payload in configs.items():
                package.writestr(path, payload)
            if model_settings:
                package.writestr("Metadata/model_settings.config", model_settings)
            package.writestr("Metadata/AnycubicSlicer.config", json.dumps({
                "generator": "AutoSlice", "target": "Anycubic Slicer",
                "exporter": "universal-native-v1",
                "original_project_name": document.preservation.original_project_name,
            }, indent=2))
        payload = output.getvalue()
        validate_3mf(payload).require_valid()
        report = _native_report(document, material_items).with_weighted_score()
        return ExportResult(payload, SlicerType.ANYCUBIC, report)


def _build_model(document: Universal3MFDocument) -> tuple[bytes, dict[str, str], int]:
    ET.register_namespace("", CORE_NS)
    root = ET.Element(f"{{{CORE_NS}}}model", {"unit": "millimeter", "{http://www.w3.org/XML/1998/namespace}lang": "en-US"})
    for name, value in (
        ("Title", document.preservation.original_project_name or document.metadata.title),
        ("Application", "AutoSlice — Universal3MF native Anycubic exporter"),
    ):
        if value:
            element = ET.SubElement(root, f"{{{CORE_NS}}}metadata", {"name": name})
            element.text = value
    resources = ET.SubElement(root, f"{{{CORE_NS}}}resources")
    build = ET.SubElement(root, f"{{{CORE_NS}}}build")
    next_id = 1
    object_ids: dict[str, str] = {}
    for obj in document.objects:
        object_ids[obj.object_id] = str(next_id)
        next_id += 1
    resource_ids: dict[str, str] = {}
    for group in document.resources.material_groups:
        resource_ids[group.resource_id] = str(next_id)
        next_id += 1
    slot_group_id = None
    if document.tool_assignments:
        slot_group_id = str(next_id)
        next_id += 1
    for texture in document.resources.textures:
        resource_ids[texture.resource_id] = str(next_id)
        next_id += 1
    for group in document.resources.texture_groups:
        resource_ids[group.resource_id] = str(next_id)
        next_id += 1
    for group in document.resources.material_groups:
        element = ET.SubElement(resources, f"{{{CORE_NS}}}basematerials", {"id": resource_ids[group.resource_id]})
        for material in group.materials:
            attributes = {"name": material.name or material.material_id}
            if material.color:
                attributes["displaycolor"] = material.color
            ET.SubElement(element, f"{{{CORE_NS}}}base", attributes)
    if slot_group_id:
        element = ET.SubElement(resources, f"{{{CORE_NS}}}basematerials", {"id": slot_group_id})
        materials_by_id = {material.material_id: material for material in document.materials}
        for assignment in sorted(document.tool_assignments, key=lambda item: item.tool_index):
            material = materials_by_id.get(assignment.material_id or "")
            attributes = {"name": material.name if material else (assignment.filament_type or f"Tool {assignment.tool_index + 1}")}
            color = assignment.color or (material.color if material else None)
            if color:
                attributes["displaycolor"] = color
            ET.SubElement(element, f"{{{CORE_NS}}}base", attributes)
    for texture in document.resources.textures:
        attributes = {"id": resource_ids[texture.resource_id], "path": texture.path}
        if texture.content_type:
            attributes["contenttype"] = texture.content_type
        if texture.tile_style_u:
            attributes["tilestyleu"] = texture.tile_style_u
        if texture.tile_style_v:
            attributes["tilestylev"] = texture.tile_style_v
        ET.SubElement(resources, f"{{{CORE_NS}}}texture2d", attributes)
    for group in document.resources.texture_groups:
        element = ET.SubElement(resources, f"{{{CORE_NS}}}texture2dgroup", {
            "id": resource_ids[group.resource_id], "texid": resource_ids[group.texture_resource_id],
        })
        for coordinate in group.coordinates:
            ET.SubElement(element, f"{{{CORE_NS}}}tex2coord", {"u": str(coordinate.u), "v": str(coordinate.v)})
    slot_by_material = {assignment.material_id: assignment.tool_index for assignment in document.tool_assignments if assignment.material_id}
    for obj in document.objects:
        attributes = {"id": object_ids[obj.object_id], "type": "model", "name": obj.name or f"object_{obj.object_id}"}
        if obj.material_resource_id in resource_ids:
            attributes["pid"] = resource_ids[obj.material_resource_id]
            if obj.material_index is not None:
                attributes["pindex"] = str(obj.material_index)
        elif slot_group_id and obj.material_resource_id in slot_by_material:
            attributes["pid"] = slot_group_id
            attributes["pindex"] = str(slot_by_material[obj.material_resource_id])
        object_element = ET.SubElement(resources, f"{{{CORE_NS}}}object", attributes)
        if obj.mesh is not None:
            mesh = ET.SubElement(object_element, f"{{{CORE_NS}}}mesh")
            vertices = ET.SubElement(mesh, f"{{{CORE_NS}}}vertices")
            for x, y, z in obj.mesh.vertices:
                ET.SubElement(vertices, f"{{{CORE_NS}}}vertex", {"x": str(x), "y": str(y), "z": str(z)})
            triangles = ET.SubElement(mesh, f"{{{CORE_NS}}}triangles")
            for triangle in obj.mesh.triangles:
                values = {"v1": str(triangle.vertices[0]), "v2": str(triangle.vertices[1]), "v3": str(triangle.vertices[2])}
                if triangle.property_resource_id in resource_ids:
                    values["pid"] = resource_ids[triangle.property_resource_id]
                    for key, prop in zip(("p1", "p2", "p3"), triangle.property_indices):
                        if prop is not None:
                            values[key] = str(prop)
                ET.SubElement(triangles, f"{{{CORE_NS}}}triangle", values)
        if obj.components:
            components = ET.SubElement(object_element, f"{{{CORE_NS}}}components")
            for component in obj.components:
                ET.SubElement(components, f"{{{CORE_NS}}}component", {
                    "objectid": object_ids[component.object_id], "transform": _transform(component.transform.values),
                })
    for item in document.build.items:
        ET.SubElement(build, f"{{{CORE_NS}}}item", {
            "objectid": object_ids[item.object_id], "transform": _transform(item.transform.values),
        })
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), object_ids, len(slot_by_material)


def _transform(values: tuple[float, ...]) -> str:
    return " ".join(str(value) for value in values)


def _build_explicit_model_settings(document: Universal3MFDocument, object_ids: dict[str, str]) -> str | None:
    slots = {assignment.material_id: assignment.tool_index + 1 for assignment in document.tool_assignments if assignment.material_id}
    mapped = [(obj, slots[obj.material_resource_id]) for obj in document.objects if obj.material_resource_id in slots]
    if not mapped:
        return None
    root = ET.Element("config")
    for obj, slot in mapped:
        element = ET.SubElement(root, "object", {"id": object_ids[obj.object_id]})
        ET.SubElement(element, "metadata", {"key": "extruder", "value": str(slot)})
        ET.SubElement(element, "metadata", {"key": "source_object_id", "value": obj.object_id})
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def _safe_assets(document: Universal3MFDocument) -> dict[str, bytes]:
    blocked = {"[Content_Types].xml", "_rels/.rels", document.package.primary_model_path}
    assets = {
        resource.path: resource.payload for resource in document.resources.opaque
        if resource.policy is PreservationPolicy.SAFE_TO_COPY and resource.path not in blocked
    }
    assets.update({texture.path: texture.payload for texture in document.resources.textures if texture.payload is not None})
    return assets


def _native_report(document: Universal3MFDocument, material_items: int) -> TranslationReport:
    items = [
        TranslationItem("object_identity", TranslationStatus.SUPPORTED, Severity.INFO, target_value=f"{len(document.objects)} objects", reason="Objects and component references are written separately."),
        TranslationItem("build_transforms", TranslationStatus.SUPPORTED, Severity.INFO, target_value=f"{len(document.build.items)} build items", reason="Build and component transforms are retained."),
    ]
    if document.tool_assignments:
        status = TranslationStatus.SUPPORTED if material_items else TranslationStatus.UNSUPPORTED
        items.append(TranslationItem("material_mapping", status, Severity.HIGH if status is TranslationStatus.UNSUPPORTED else Severity.INFO, reason="Only explicit Universal3MF material-to-tool assignments are exported; no round-robin fallback is used."))
    safe_opaque = [item for item in document.resources.opaque if item.policy is PreservationPolicy.SAFE_TO_COPY]
    withheld_opaque = [item for item in document.resources.opaque if item.policy is not PreservationPolicy.SAFE_TO_COPY]
    if safe_opaque:
        items.append(TranslationItem(
            "target_safe_opaque_data", TranslationStatus.PRESERVED_OPAQUE, Severity.LOW,
            target_value=f"{len(safe_opaque)} package parts",
            reason="Target-safe opaque package parts are copied without semantic modification.",
        ))
    if withheld_opaque:
        items.append(TranslationItem(
            "source_specific_opaque_data", TranslationStatus.UNSUPPORTED, Severity.MEDIUM,
            source_value=f"{len(withheld_opaque)} package parts", target_value="not copied",
            reason="Source-only or review-required opaque data remains in Universal3MF but is withheld from cross-slicer output.",
        ))
    return TranslationReport(tuple(items))
