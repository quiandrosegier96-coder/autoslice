"""Read-only Universal3MF geometry and process analysis."""

from math import sqrt

from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.geometry import Mesh
from app.threemf.intelligence.models import (
    ObjectAnalysis,
    PlanStatus,
    ProjectAnalysis,
    TargetProfile,
)


def _mesh_metrics(
    mesh: Mesh,
) -> tuple[tuple[tuple[float, float, float], tuple[float, float, float]], float, float]:
    if not mesh.vertices:
        zero = (0.0, 0.0, 0.0)
        return (zero, zero), 0.0, 0.0
    mins = tuple(min(vertex[i] for vertex in mesh.vertices) for i in range(3))
    maxs = tuple(max(vertex[i] for vertex in mesh.vertices) for i in range(3))
    signed_volume = surface = 0.0
    for triangle in mesh.triangles:
        a, b, c = (mesh.vertices[index] for index in triangle.vertices)
        cross = (
            (b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]),
            (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
            (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]),
        )
        surface += 0.5 * sqrt(sum(value * value for value in cross))
        signed_volume += (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        ) / 6.0
    return (mins, maxs), abs(signed_volume), surface


class ProjectAnalyzer:
    def analyze(
        self, document: Universal3MFDocument, target: TargetProfile | None = None
    ) -> ProjectAnalysis:
        objects: list[ObjectAnalysis] = []
        for obj in sorted(document.objects, key=lambda item: item.object_id):
            if obj.mesh is None:
                continue
            bounds, volume, surface = _mesh_metrics(obj.mesh)
            dimensions = tuple(round(bounds[1][i] - bounds[0][i], 6) for i in range(3))
            objects.append(
                ObjectAnalysis(
                    obj.object_id,
                    dimensions,
                    bounds,
                    volume,
                    surface,
                    obj.material_resource_id,
                    min(dimensions, default=0) < 0.8,
                )
            )
        if objects:
            mins = tuple(min(item.bounding_box_mm[0][i] for item in objects) for i in range(3))
            maxs = tuple(max(item.bounding_box_mm[1][i] for item in objects) for i in range(3))
        else:
            mins = maxs = (0.0, 0.0, 0.0)
        dimensions = tuple(round(maxs[i] - mins[i], 6) for i in range(3))
        status = None
        if target:
            ratios = tuple(dimensions[i] / target.printer.build_volume_mm[i] for i in range(3))
            status = (
                PlanStatus.OUTSIDE_BUILD_VOLUME
                if any(ratio > 1 for ratio in ratios)
                else (
                    PlanStatus.NEAR_LIMIT
                    if any(ratio >= 0.9 for ratio in ratios)
                    else PlanStatus.WITHIN_BUILD_VOLUME
                )
            )
        settings = tuple(
            (name, getattr(document.process, name))
            for name in (
                "layer_height_mm",
                "first_layer_height_mm",
                "wall_count",
                "top_layers",
                "bottom_layers",
                "infill_density_percent",
                "nozzle_temperature_c",
                "bed_temperature_c",
                "fan_speed_percent",
                "print_speed_mm_s",
            )
            if getattr(document.process, name) is not None
        )
        materials = tuple(
            sorted(
                {item.material_id for item in document.materials}
                | {item.material_id for item in document.tool_assignments if item.material_id}
            )
        )
        mapping = tuple(
            (obj.object_id, obj.material_resource_id)
            for obj in sorted(document.objects, key=lambda item: item.object_id)
        )
        return ProjectAnalysis(
            len(document.objects),
            dimensions,
            (mins, maxs),
            sum(item.volume_mm3 for item in objects),
            sum(item.surface_area_mm2 for item in objects),
            materials,
            mapping,
            settings,
            tuple(objects),
            status,
            overhang_indicator=False,
            small_feature_indicator=any(item.thin_feature_warning for item in objects),
        )
