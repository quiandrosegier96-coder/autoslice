"""Conservative enrichment shared by Bambu and Anycubic parser adapters."""

from dataclasses import replace

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.container.xml import local_name, parse_xml
from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.geometry import ObjectRole
from app.threemf.parsers.project_settings import filament_resources, read_project_settings, settings_from_project

MODEL_SETTINGS_PATH = "Metadata/model_settings.config"


def enrich_prusaslicer_family(document: Universal3MFDocument, container: ThreeMFContainer) -> Universal3MFDocument:
    project = read_project_settings(container)
    slot_materials, tools = filament_resources(project)
    explicit_slots, roles = _object_mappings(container)
    enriched_objects = []
    for obj in document.objects:
        slot = explicit_slots.get(obj.object_id)
        role = roles.get(obj.object_id, obj.role)
        enriched_objects.append(replace(
            obj, role=role, object_type=role.value if role is not ObjectRole.UNKNOWN else obj.object_type,
            material_resource_id=f"filament-slot:{slot}" if slot is not None else obj.material_resource_id,
            material_index=None if slot is not None else obj.material_index,
        ))
    existing_ids = {material.material_id for material in document.materials}
    materials = document.materials + tuple(material for material in slot_materials if material.material_id not in existing_ids)
    return replace(document, objects=tuple(enriched_objects), process=settings_from_project(project), materials=materials, tool_assignments=tools)


def _object_mappings(container: ThreeMFContainer) -> tuple[dict[str, int], dict[str, ObjectRole]]:
    if not container.exists(MODEL_SETTINGS_PATH):
        return {}, {}
    try:
        root = parse_xml(container.read(MODEL_SETTINGS_PATH), MODEL_SETTINGS_PATH)
    except ValueError:
        return {}, {}
    slots: dict[str, int] = {}
    roles: dict[str, ObjectRole] = {}
    role_names = {role.value: role for role in ObjectRole}
    for element in root.iter():
        if local_name(element.tag) not in {"object", "part"}:
            continue
        object_id = element.attrib.get("id")
        if not object_id:
            continue
        subtype = element.attrib.get("subtype", "")
        if subtype in role_names:
            roles[object_id] = role_names[subtype]
        for child in element:
            if local_name(child.tag) != "metadata":
                continue
            key = child.attrib.get("key", "")
            value = child.attrib.get("value", child.text or "")
            if key in {"extruder", "filament_id"}:
                try:
                    slots[object_id] = int(value)
                except ValueError:
                    pass
    return slots, roles
