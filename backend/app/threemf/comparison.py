"""Semantic comparison for legacy and Universal3MF package outputs."""

from dataclasses import dataclass

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.parsers.core import CoreThreeMFParser
from app.threemf.parsers.project_settings import read_project_settings


@dataclass(frozen=True)
class PackageSemantics:
    object_count: int
    mesh_count: int
    vertex_count: int
    triangle_count: int
    material_count: int
    tool_count: int
    build_item_count: int
    dimensions_mm: tuple[float, float, float] | None
    build_transforms: tuple[tuple[float, ...], ...]
    filament_count: int
    print_settings: tuple[tuple[str, str], ...]
    package_paths: tuple[str, ...]


@dataclass(frozen=True)
class SemanticComparison:
    left: PackageSemantics
    right: PackageSemantics


def inspect_package(payload: bytes) -> PackageSemantics:
    container = ThreeMFContainer.from_bytes(payload)
    document = CoreThreeMFParser().parse(container)
    meshes = [obj.mesh for obj in document.objects if obj.mesh is not None]
    vertices = [vertex for mesh in meshes for vertex in mesh.vertices]
    dimensions = None
    if vertices:
        dimensions = tuple(max(vertex[axis] for vertex in vertices) - min(vertex[axis] for vertex in vertices) for axis in range(3))
    project = read_project_settings(container)
    filaments = project.get("filament_type", [])
    filament_count = len(filaments) if isinstance(filaments, list) else (1 if filaments else 0)
    important = ("layer_height", "wall_loops", "sparse_infill_density", "sparse_infill_pattern", "nozzle_temperature", "bed_temperature")
    return PackageSemantics(
        len(document.objects), len(meshes), sum(len(mesh.vertices) for mesh in meshes),
        sum(len(mesh.triangles) for mesh in meshes), len(document.materials),
        len(document.tool_assignments), len(document.build.items),
        dimensions, tuple(item.transform.values for item in document.build.items), filament_count,
        tuple((key, str(project[key])) for key in important if key in project), container.paths,
    )


def compare_packages(left: bytes, right: bytes) -> SemanticComparison:
    return SemanticComparison(inspect_package(left), inspect_package(right))
