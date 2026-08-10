"""Self-consistency validation for generated or uploaded 3MF packages."""

from dataclasses import dataclass

from app.threemf.container.opc import primary_model_path
from app.threemf.container.reader import ThreeMFContainer
from app.threemf.container.xml import parse_xml
from app.threemf.domain.diagnostics import Diagnostic, Severity
from app.threemf.parsers.core import CoreThreeMFParser


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    diagnostics: tuple[Diagnostic, ...] = ()

    def require_valid(self) -> None:
        if not self.valid:
            messages = "; ".join(item.message for item in self.diagnostics)
            raise ValueError(f"Invalid 3MF output: {messages}")


def validate_3mf(value: bytes | ThreeMFContainer) -> ValidationResult:
    diagnostics: list[Diagnostic] = []
    try:
        container = value if isinstance(value, ThreeMFContainer) else ThreeMFContainer.from_bytes(value)
    except ValueError as exc:
        return ValidationResult(False, (Diagnostic("package.invalid_zip", str(exc), Severity.CRITICAL),))
    if not container.exists("[Content_Types].xml"):
        diagnostics.append(Diagnostic("package.content_types_missing", "[Content_Types].xml is missing.", Severity.CRITICAL))
    else:
        try:
            parse_xml(container.read("[Content_Types].xml"), "[Content_Types].xml")
        except ValueError as exc:
            diagnostics.append(Diagnostic("package.content_types_invalid", str(exc), Severity.CRITICAL))
    if not container.exists("_rels/.rels"):
        diagnostics.append(Diagnostic("package.relationships_missing", "_rels/.rels is missing.", Severity.CRITICAL))
    try:
        model_path = primary_model_path(container)
        parse_xml(container.read(model_path), model_path)
        document = CoreThreeMFParser().parse(container)
        _validate_document(document, container, diagnostics)
    except ValueError as exc:
        diagnostics.append(Diagnostic("model.invalid", str(exc), Severity.CRITICAL))
    return ValidationResult(not any(item.severity in {Severity.HIGH, Severity.CRITICAL} for item in diagnostics), tuple(diagnostics))


def _validate_document(document, container: ThreeMFContainer, diagnostics: list[Diagnostic]) -> None:
    resource_ids = {group.resource_id for group in document.resources.material_groups}
    resource_ids.update(group.resource_id for group in document.resources.texture_groups)
    for obj in document.objects:
        if obj.material_resource_id and obj.material_resource_id not in resource_ids:
            diagnostics.append(Diagnostic("material.object_reference", f"Object {obj.object_id} references missing resource {obj.material_resource_id}.", Severity.HIGH))
        if obj.mesh:
            vertex_count = len(obj.mesh.vertices)
            for index, triangle in enumerate(obj.mesh.triangles):
                if min(triangle.vertices) < 0 or max(triangle.vertices) >= vertex_count:
                    diagnostics.append(Diagnostic("mesh.triangle_index", f"Object {obj.object_id} triangle {index} has an invalid vertex index.", Severity.CRITICAL))
                if triangle.property_resource_id and triangle.property_resource_id not in resource_ids:
                    diagnostics.append(Diagnostic("material.triangle_reference", f"Object {obj.object_id} triangle {index} references missing resource {triangle.property_resource_id}.", Severity.HIGH))
    texture_ids = {texture.resource_id for texture in document.resources.textures}
    for texture in document.resources.textures:
        if not texture.path or not container.exists(texture.path):
            diagnostics.append(Diagnostic("texture.part_missing", f"Texture {texture.resource_id} has no reachable package part.", Severity.HIGH))
    for group in document.resources.texture_groups:
        if group.texture_resource_id not in texture_ids:
            diagnostics.append(Diagnostic("texture.group_reference", f"Texture group {group.resource_id} references missing texture {group.texture_resource_id}.", Severity.HIGH))
