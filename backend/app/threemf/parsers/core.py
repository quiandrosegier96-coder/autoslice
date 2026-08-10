"""Parser for slicer-neutral 3MF core resources and scene structure."""

import xml.etree.ElementTree as ET

from app.threemf.container.opc import primary_model_path
from app.threemf.container.reader import ThreeMFContainer
from app.threemf.container.xml import local_name, parse_xml
from app.threemf.detection.detector import detect_3mf
from app.threemf.domain.build import Build, BuildItem
from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.geometry import ComponentReference, Mesh, ModelObject, ObjectRole, Transform, Triangle
from app.threemf.domain.materials import Material, MaterialGroup
from app.threemf.domain.metadata import PackageInfo, PreservationData, ProjectMetadata, SourceInfo
from app.threemf.domain.resources import OpaqueResource, PreservationPolicy, Resources, TextureCoordinate, TextureGroup, TextureResource
from app.threemf.parsers.base import ThreeMFParser

_UNIT_TO_MM = {"micron": 0.001, "millimeter": 1.0, "centimeter": 10.0, "meter": 1000.0, "inch": 25.4, "foot": 304.8}
_KNOWN_PACKAGE_PARTS = {"[Content_Types].xml", "_rels/.rels"}


def _children(element, name: str):
    return [child for child in element if local_name(child.tag) == name]


def _child(element, name: str):
    return next((child for child in element if local_name(child.tag) == name), None)


def _role(value: str) -> ObjectRole:
    try:
        return ObjectRole(value)
    except ValueError:
        return ObjectRole.MODEL if value == "model" else ObjectRole.UNKNOWN


class CoreThreeMFParser(ThreeMFParser):
    def can_parse(self, container: ThreeMFContainer):
        return detect_3mf(container)

    def parse(self, container: ThreeMFContainer) -> Universal3MFDocument:
        model_path = primary_model_path(container)
        root = parse_xml(container.read(model_path), model_path)
        scale = _UNIT_TO_MM.get(root.attrib.get("unit", "millimeter"), 1.0)
        resources_element = _child(root, "resources")
        objects: list[ModelObject] = []
        groups: list[MaterialGroup] = []
        materials: list[Material] = []
        textures: list[TextureResource] = []
        texture_groups: list[TextureGroup] = []
        resource_opaque: list[OpaqueResource] = []
        if resources_element is not None:
            for element in resources_element:
                tag = local_name(element.tag)
                if tag == "object":
                    objects.append(self._parse_object(element, model_path, scale))
                elif tag == "basematerials":
                    group = self._parse_material_group(element)
                    groups.append(group)
                    materials.extend(group.materials)
                elif tag == "texture2d":
                    texture_path = element.attrib.get("path", "").lstrip("/")
                    textures.append(TextureResource(
                        resource_id=element.attrib["id"], path=texture_path,
                        payload=container.read(texture_path) if texture_path and container.exists(texture_path) else None,
                        content_type=element.attrib.get("contenttype"), tile_style_u=element.attrib.get("tilestyleu"),
                        tile_style_v=element.attrib.get("tilestylev"), box=element.attrib.get("box"),
                    ))
                elif tag == "texture2dgroup":
                    texture_groups.append(TextureGroup(
                        resource_id=element.attrib["id"], texture_resource_id=element.attrib.get("texid", ""),
                        coordinates=tuple(TextureCoordinate(float(coord.attrib["u"]), float(coord.attrib["v"])) for coord in _children(element, "tex2coord")),
                    ))
                else:
                    resource_opaque.append(OpaqueResource(
                        identifier=f"{model_path}#resource:{element.attrib.get('id', tag)}",
                        source="core", path=model_path, payload=ET.tostring(element, encoding="utf-8"),
                        namespace=element.tag.split("}", 1)[0].lstrip("{") if "}" in element.tag else None,
                        content_type="application/xml", policy=PreservationPolicy.REVIEW_REQUIRED,
                    ))
        build_element = _child(root, "build")
        build_items = () if build_element is None else tuple(
            BuildItem(item.attrib["objectid"], Transform.parse(item.attrib.get("transform")), part_number=item.attrib.get("partnumber"))
            for item in _children(build_element, "item")
        )
        metadata_pairs = tuple((item.attrib.get("name", ""), item.text or "") for item in _children(root, "metadata"))
        metadata_map = dict(metadata_pairs)
        detection = detect_3mf(container)
        opaque = tuple(resource_opaque) + tuple(
            OpaqueResource(
                identifier=path, source=detection.slicer.value, path=path, payload=container.read(path),
                policy=PreservationPolicy.SOURCE_ONLY if path.startswith("Metadata/") else PreservationPolicy.SAFE_TO_COPY,
            )
            for path in container.paths if path not in _KNOWN_PACKAGE_PARTS | {model_path} and not path.startswith("3D/Textures/")
        )
        return Universal3MFDocument(
            schema_version="1.0",
            source=SourceInfo(detection.slicer, detection.version, detection.confidence, detection.evidence, container.filename),
            package=PackageInfo(model_path, unit="millimeter", paths=container.paths),
            metadata=ProjectMetadata(
                title=metadata_map.get("Title"), description=metadata_map.get("Description"),
                creator=metadata_map.get("Designer"), application=metadata_map.get("Application"), values=metadata_pairs,
            ),
            resources=Resources(tuple(groups), tuple(textures), tuple(texture_groups), opaque),
            objects=tuple(objects), build=Build(build_items), materials=tuple(materials),
            preservation=PreservationData(metadata_map.get("Title"), opaque),
        )

    def _parse_object(self, element, source_path: str, scale: float) -> ModelObject:
        mesh_element = _child(element, "mesh")
        mesh = None
        if mesh_element is not None:
            vertices_element = _child(mesh_element, "vertices")
            triangles_element = _child(mesh_element, "triangles")
            vertices = () if vertices_element is None else tuple(
                (float(v.attrib["x"]) * scale, float(v.attrib["y"]) * scale, float(v.attrib["z"]) * scale)
                for v in _children(vertices_element, "vertex")
            )
            triangles = () if triangles_element is None else tuple(
                Triangle(
                    (int(t.attrib["v1"]), int(t.attrib["v2"]), int(t.attrib["v3"])), t.attrib.get("pid"),
                    tuple(int(t.attrib[key]) if key in t.attrib else None for key in ("p1", "p2", "p3")),
                ) for t in _children(triangles_element, "triangle")
            )
            mesh = Mesh(vertices, triangles)
        components_element = _child(element, "components")
        components = () if components_element is None else tuple(
            ComponentReference(component.attrib["objectid"], Transform.parse(component.attrib.get("transform")))
            for component in _children(components_element, "component")
        )
        object_type = element.attrib.get("type", "model")
        return ModelObject(
            object_id=element.attrib["id"], name=element.attrib.get("name", ""), object_type=object_type,
            role=_role(object_type), mesh=mesh, components=components,
            material_resource_id=element.attrib.get("pid"),
            material_index=int(element.attrib["pindex"]) if "pindex" in element.attrib else None,
            source_path=source_path,
        )

    def _parse_material_group(self, element) -> MaterialGroup:
        resource_id = element.attrib["id"]
        values = tuple(
            Material(f"{resource_id}:{index}", name=base.attrib.get("name", ""), color=base.attrib.get("displaycolor"))
            for index, base in enumerate(_children(element, "base"))
        )
        return MaterialGroup(resource_id, materials=values)
