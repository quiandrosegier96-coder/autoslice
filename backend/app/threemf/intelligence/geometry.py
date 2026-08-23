"""Safe, deterministic geometry intelligence for Universal3MF meshes."""

from dataclasses import dataclass
from enum import Enum
from math import acos, degrees, isfinite, sqrt
from time import perf_counter

from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.geometry import Mesh
from app.threemf.intelligence.models import Confidence, TargetProfile

MAX_TRIANGLES = 1_000_000
MAX_COORDINATE_MM = 1_000_000.0


class PrintabilityStatus(str, Enum):
    GOOD = "good"
    WARNING = "warning"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class GeometryDiagnostic:
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class GeometryHealthReport:
    status: PrintabilityStatus
    valid_mesh: bool
    closed_surface: bool | None
    duplicate_triangles: int
    degenerate_triangles: int
    non_manifold_edges: int
    open_boundary_edges: int
    diagnostics: tuple[GeometryDiagnostic, ...]


@dataclass(frozen=True)
class OverhangReport:
    threshold_degrees: float
    area_mm2: float
    percentage: float
    moderate_faces: tuple[int, ...]
    critical_faces: tuple[int, ...]
    estimated_support_required: bool


@dataclass(frozen=True)
class OrientationCandidate:
    rotation_degrees: tuple[float, float, float]
    dimensions_mm: tuple[float, float, float]
    fits_build_volume: bool
    contact_area_mm2: float
    overhang_percentage: float
    height_mm: float
    score_breakdown: tuple[tuple[str, float], ...]
    score: float


@dataclass(frozen=True)
class GeometryOrientationRecommendation:
    current_transform: tuple[float, ...]
    recommended_transform: tuple[float, ...]
    rotation_degrees: tuple[float, float, float]
    score: float
    current_score: float
    score_breakdown: tuple[tuple[str, float], ...]
    reason: str
    confidence: Confidence
    estimated_support_reduction_percent: float
    apply_automatically: bool
    candidates: tuple[OrientationCandidate, ...]


@dataclass(frozen=True)
class ObjectPrintability:
    object_id: str
    status: PrintabilityStatus
    dimensions_mm: tuple[float, float, float]
    triangle_count: int
    center_of_mass_mm: tuple[float, float, float] | None
    principal_axes: tuple[tuple[float, float, float], ...]
    health: GeometryHealthReport
    overhangs: OverhangReport
    thin_feature_status: str
    small_feature_status: str
    wall_feasibility: str
    build_volume: str
    placement: tuple[str, ...]
    contact_area_mm2: float
    contact_ratio: float
    contact_faces: tuple[int, ...]
    orientation: GeometryOrientationRecommendation | None


@dataclass(frozen=True)
class Collision:
    first_object_id: str
    second_object_id: str
    kind: str = "OBJECT_COLLISION"


@dataclass(frozen=True)
class GeometryTimings:
    mesh_validation_ms: float
    geometry_analysis_ms: float
    overhang_analysis_ms: float
    orientation_candidates_ms: float
    collision_analysis_ms: float
    total_ms: float


@dataclass(frozen=True)
class PrintabilityReport:
    status: PrintabilityStatus
    objects: tuple[ObjectPrintability, ...]
    collisions: tuple[Collision, ...]
    project_build_volume: str
    object_spacing: str
    support_recommendations: tuple[str, ...]
    diagnostics: tuple[GeometryDiagnostic, ...]
    debug: tuple[tuple[str, object], ...]
    timings: GeometryTimings


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def _rotate(vertex, rotation):
    x, y, z = vertex
    if rotation == (90.0, 0.0, 0.0):
        return (x, -z, y)
    if rotation == (-90.0, 0.0, 0.0):
        return (x, z, -y)
    if rotation == (0.0, 90.0, 0.0):
        return (z, y, -x)
    if rotation == (0.0, -90.0, 0.0):
        return (-z, y, x)
    if rotation == (180.0, 0.0, 0.0):
        return (x, -y, -z)
    return vertex


def _metrics(mesh: Mesh, rotation=(0.0, 0.0, 0.0), threshold=45.0):
    vertices = tuple(_rotate(v, rotation) for v in mesh.vertices)
    mins = tuple(min(v[i] for v in vertices) for i in range(3))
    maxs = tuple(max(v[i] for v in vertices) for i in range(3))
    dims = tuple(maxs[i] - mins[i] for i in range(3))
    total = overhang = contact = 0.0
    moderate, critical, contacts = [], [], []
    for index, tri in enumerate(mesh.triangles):
        a, b, c = (vertices[i] for i in tri.vertices)
        normal = _cross(_sub(b, a), _sub(c, a))
        length = sqrt(sum(v * v for v in normal))
        area = length / 2
        if not length:
            continue
        nz = normal[2] / length
        total += area
        angle = degrees(acos(max(-1.0, min(1.0, -nz))))
        on_build_plane = max(a[2], b[2], c[2]) <= mins[2] + max(0.05, dims[2] * 0.002)
        if nz < 0 and angle < threshold and not on_build_plane:
            overhang += area
            (critical if angle < threshold * 0.5 else moderate).append(index)
        if on_build_plane:
            contact += area * abs(nz)
            contacts.append(index)
    return (
        vertices,
        mins,
        maxs,
        dims,
        total,
        overhang,
        contact,
        tuple(contacts),
        tuple(moderate),
        tuple(critical),
    )


def validate_mesh(mesh: Mesh) -> GeometryHealthReport:
    diagnostics = []
    valid = True
    if len(mesh.triangles) > MAX_TRIANGLES:
        return GeometryHealthReport(
            PrintabilityStatus.BLOCKED,
            False,
            None,
            0,
            0,
            0,
            0,
            (GeometryDiagnostic("RESOURCE_LIMIT", "error", "Triangle resource limit exceeded."),),
        )
    for vertex in mesh.vertices:
        if not all(isfinite(v) and abs(v) <= MAX_COORDINATE_MM for v in vertex):
            valid = False
            diagnostics.append(
                GeometryDiagnostic(
                    "INVALID_COORDINATE",
                    "error",
                    "Mesh contains non-finite or extreme coordinates.",
                )
            )
            break
    seen = set()
    duplicate = degenerate = 0
    edges = {}
    for tri in mesh.triangles:
        if any(i < 0 or i >= len(mesh.vertices) for i in tri.vertices):
            valid = False
            diagnostics.append(
                GeometryDiagnostic(
                    "INVALID_INDEX", "error", "Triangle references an invalid vertex."
                )
            )
            continue
        key = tuple(sorted(tri.vertices))
        if key in seen:
            duplicate += 1
        seen.add(key)
        a, b, c = (mesh.vertices[i] for i in tri.vertices)
        if (
            len(set(tri.vertices)) < 3
            or sqrt(sum(v * v for v in _cross(_sub(b, a), _sub(c, a)))) <= 1e-12
        ):
            degenerate += 1
        for edge in (
            (tri.vertices[0], tri.vertices[1]),
            (tri.vertices[1], tri.vertices[2]),
            (tri.vertices[2], tri.vertices[0]),
        ):
            edge = tuple(sorted(edge))
            edges[edge] = edges.get(edge, 0) + 1
    boundary = sum(v == 1 for v in edges.values())
    nonmanifold = sum(v > 2 for v in edges.values())
    if duplicate:
        diagnostics.append(
            GeometryDiagnostic(
                "DUPLICATE_TRIANGLES", "warning", f"{duplicate} duplicate triangles detected."
            )
        )
    if degenerate:
        diagnostics.append(
            GeometryDiagnostic(
                "DEGENERATE_TRIANGLES", "warning", f"{degenerate} degenerate triangles detected."
            )
        )
    if boundary:
        diagnostics.append(
            GeometryDiagnostic(
                "OPEN_BOUNDARIES", "warning", f"{boundary} open boundary edges detected."
            )
        )
    if nonmanifold:
        diagnostics.append(
            GeometryDiagnostic(
                "NON_MANIFOLD", "warning", f"{nonmanifold} non-manifold edges detected."
            )
        )
    status = (
        PrintabilityStatus.BLOCKED
        if not valid
        else (PrintabilityStatus.WARNING if diagnostics else PrintabilityStatus.GOOD)
    )
    return GeometryHealthReport(
        status,
        valid,
        not boundary and not nonmanifold,
        duplicate,
        degenerate,
        nonmanifold,
        boundary,
        tuple(diagnostics),
    )


class GeometryAnalyzer:
    def analyze(
        self, document: Universal3MFDocument, target: TargetProfile, profile
    ) -> PrintabilityReport:
        started = perf_counter()
        validation_ms = geometry_ms = overhang_ms = orientation_ms = 0.0
        results = []
        boxes = []
        diagnostics = []
        mesh_objects = [
            obj
            for obj in sorted(document.objects, key=lambda o: o.object_id)
            if obj.mesh and obj.mesh.vertices
        ]
        for obj in mesh_objects:
            mark = perf_counter()
            health = validate_mesh(obj.mesh)
            validation_ms += (perf_counter() - mark) * 1000
            if not health.valid_mesh:
                diagnostics.extend(health.diagnostics)
                continue
            mark = perf_counter()
            base = _metrics(obj.mesh, threshold=profile.overhang_threshold_degrees)
            geometry_ms += (perf_counter() - mark) * 1000
            _, mins, maxs, dims, total, overhang, contact, contacts, moderate, critical = base
            boxes.append((obj.object_id, mins, maxs))
            overhang_ms += 0.0
            fits = all(dims[i] <= target.printer.build_volume_mm[i] for i in range(3))
            near = fits and any(
                dims[i] >= target.printer.build_volume_mm[i] * 0.9 for i in range(3)
            )
            placement = tuple(
                code
                for code, yes in (
                    ("BELOW_BUILD_PLATE", mins[2] < -1e-6),
                    ("ABOVE_BUILD_PLATE", mins[2] > 1e-6),
                    ("INTERSECTS_BUILD_PLATE", mins[2] <= 0 <= maxs[2]),
                )
                if yes
            )
            candidates = []
            mark = perf_counter()
            for rotation in (
                (0.0, 0.0, 0.0),
                (90.0, 0.0, 0.0),
                (-90.0, 0.0, 0.0),
                (0.0, 90.0, 0.0),
                (0.0, -90.0, 0.0),
                (180.0, 0.0, 0.0),
            ):
                m = _metrics(obj.mesh, rotation, profile.overhang_threshold_degrees)
                d = m[3]
                fit = all(d[i] <= target.printer.build_volume_mm[i] for i in range(3))
                pct = 100 * m[5] / m[4] if m[4] else 0
                footprint = max(d[0] * d[1], 1e-9)
                contact_score = min(100.0, 100 * m[6] / footprint)
                overhang_score = max(0.0, 100 - pct * 2)
                height_score = max(0.0, 100 - 100 * d[2] / target.printer.build_volume_mm[2])
                stability = min(100.0, 100 * sqrt(footprint) / max(d[2], 0.001))
                fit_score = 100.0 if fit else 0.0
                score = (
                    0.3 * fit_score
                    + 0.25 * contact_score
                    + 0.25 * overhang_score
                    + 0.1 * height_score
                    + 0.1 * stability
                )
                candidates.append(
                    OrientationCandidate(
                        rotation,
                        d,
                        fit,
                        round(m[6], 4),
                        round(pct, 4),
                        d[2],
                        (
                            ("fit", fit_score),
                            ("contact", round(contact_score, 2)),
                            ("overhang", round(overhang_score, 2)),
                            ("height", round(height_score, 2)),
                            ("stability", round(stability, 2)),
                        ),
                        round(score, 2),
                    )
                )
            candidates = sorted(candidates, key=lambda c: (-c.score, c.rotation_degrees))
            current = next(c for c in candidates if c.rotation_degrees == (0.0, 0.0, 0.0))
            best = candidates[0]
            gap = best.score - candidates[1].score
            improvement = best.score - current.score
            confidence = (
                Confidence.HIGH
                if gap >= 5 and improvement >= profile.orientation_improvement_threshold
                else (Confidence.MEDIUM if gap >= 2 else Confidence.LOW)
            )
            auto = best.rotation_degrees != (0.0, 0.0, 0.0) and best.fits_build_volume
            orientation = GeometryOrientationRecommendation(
                (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
                _transform(best.rotation_degrees),
                best.rotation_degrees,
                best.score,
                current.score,
                best.score_breakdown,
                "Improves measurable build contact, overhang, height, stability, or fit.",
                confidence,
                round(max(0.0, current.overhang_percentage - best.overhang_percentage), 2),
                auto,
                tuple(candidates),
            )
            orientation_ms += (perf_counter() - mark) * 1000
            thin = min(dims) < target.nozzle.line_width_range_mm[0]
            tiny = min(dims) < target.nozzle.diameter_mm * 0.5
            wall = document.process.wall_count or 0
            line = document.process.extrusion_width_mm or target.nozzle.diameter_mm
            status = (
                PrintabilityStatus.BLOCKED
                if not fits or health.status is PrintabilityStatus.BLOCKED
                else (
                    PrintabilityStatus.WARNING
                    if health.status is PrintabilityStatus.WARNING
                    or critical
                    or thin
                    or any(
                        issue in {"BELOW_BUILD_PLATE", "ABOVE_BUILD_PLATE"} for issue in placement
                    )
                    else PrintabilityStatus.GOOD
                )
            )
            results.append(
                ObjectPrintability(
                    obj.object_id,
                    status,
                    dims,
                    len(obj.mesh.triangles),
                    tuple(
                        sum(v[i] for v in obj.mesh.vertices) / len(obj.mesh.vertices)
                        for i in range(3)
                    ),
                    ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
                    health,
                    OverhangReport(
                        profile.overhang_threshold_degrees,
                        round(overhang, 4),
                        round(100 * overhang / total if total else 0, 4),
                        moderate,
                        critical,
                        bool(critical),
                    ),
                    "LIKELY_UNPRINTABLE"
                    if min(dims) < target.nozzle.diameter_mm * 0.5
                    else ("POTENTIALLY_THIN" if thin else "SAFE"),
                    "WARNING" if tiny else "SAFE",
                    "WARNING" if wall and min(dims) < wall * line else "GOOD",
                    "DOES_NOT_FIT" if not fits else ("NEAR_LIMIT" if near else "FITS"),
                    placement,
                    round(contact, 4),
                    round(contact / (dims[0] * dims[1]) if dims[0] * dims[1] else 0, 4),
                    contacts,
                    orientation,
                )
            )
        mark = perf_counter()
        collisions = []
        for i, a in enumerate(boxes):
            for b in boxes[i + 1 :]:
                if all(a[1][k] <= b[2][k] and b[1][k] <= a[2][k] for k in range(3)):
                    collisions.append(Collision(a[0], b[0]))
        collision_ms = (perf_counter() - mark) * 1000
        if collisions:
            diagnostics.append(
                GeometryDiagnostic("OBJECT_COLLISION", "warning", "Object bounding boxes overlap.")
            )
        status = (
            PrintabilityStatus.UNKNOWN
            if not results
            else (
                PrintabilityStatus.BLOCKED
                if any(o.status is PrintabilityStatus.BLOCKED for o in results)
                else (
                    PrintabilityStatus.WARNING
                    if collisions or any(o.status is PrintabilityStatus.WARNING for o in results)
                    else PrintabilityStatus.GOOD
                )
            )
        )
        timings = GeometryTimings(
            validation_ms,
            geometry_ms,
            overhang_ms,
            orientation_ms,
            collision_ms,
            (perf_counter() - started) * 1000,
        )
        supports = tuple(
            f"Supports recommended for object {o.object_id}: critical overhang faces detected."
            for o in results
            if o.overhangs.estimated_support_required
        )
        return PrintabilityReport(
            status,
            tuple(results),
            tuple(collisions),
            "PROJECT_DOES_NOT_FIT"
            if any(o.build_volume == "DOES_NOT_FIT" for o in results)
            else ("PROJECT_REQUIRES_REPOSITIONING" if collisions else "PROJECT_FITS"),
            "UNKNOWN",
            supports,
            tuple(diagnostics),
            (
                ("build_volume_box", target.printer.build_volume_mm),
                ("collision_boxes", tuple(boxes)),
            ),
            timings,
        )


def _transform(rotation):
    if rotation == (90.0, 0.0, 0.0):
        return (1.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0)
    if rotation == (-90.0, 0.0, 0.0):
        return (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0)
    if rotation == (0.0, 90.0, 0.0):
        return (0.0, 0.0, 1.0, 0.0, 1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    if rotation == (0.0, -90.0, 0.0):
        return (0.0, 0.0, -1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    if rotation == (180.0, 0.0, 0.0):
        return (1.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0)
    return (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)
