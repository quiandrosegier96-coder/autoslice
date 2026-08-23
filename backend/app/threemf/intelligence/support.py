"""Deterministic support-region analysis and planning; no support mesh generation."""

from dataclasses import dataclass
from enum import Enum
from math import acos, degrees, sqrt

from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.geometry import ObjectRole
from app.threemf.domain.settings import ConversionMode
from app.threemf.intelligence.geometry import PrintabilityReport
from app.threemf.intelligence.models import Confidence, TargetProfile


class SupportStrategy(str, Enum):
    NONE = "none"
    BUILD_PLATE_ONLY = "build_plate_only"
    NORMAL = "normal"
    TREE = "tree"
    ORGANIC = "organic"
    AUTO = "auto"


@dataclass(frozen=True)
class SupportDiagnostic:
    code: str
    message: str


@dataclass(frozen=True)
class SupportRegion:
    region_id: str
    object_id: str
    face_indices: tuple[int, ...]
    area_mm2: float
    average_angle_degrees: float
    severity: str
    build_plate_accessible: bool | None
    requirement: str
    confidence: Confidence
    centroid_mm: tuple[float, float, float]
    blocked_by_source: bool = False
    enforced_by_source: bool = False


@dataclass(frozen=True)
class SupportPlan:
    strategy: SupportStrategy
    required_regions: tuple[SupportRegion, ...]
    optional_regions: tuple[SupportRegion, ...]
    blocked_regions: tuple[SupportRegion, ...]
    estimated_support_volume_mm3: float | None
    confidence: Confidence
    diagnostics: tuple[SupportDiagnostic, ...]
    applied: bool
    preserves_source_supports: bool


def _face_data(mesh, index):
    tri = mesh.triangles[index]
    a, b, c = (mesh.vertices[i] for i in tri.vertices)
    ab = tuple(b[i] - a[i] for i in range(3))
    ac = tuple(c[i] - a[i] for i in range(3))
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    length = sqrt(sum(v * v for v in cross))
    area = length / 2
    nz = cross[2] / length if length else 0
    angle = degrees(acos(max(-1.0, min(1.0, -nz))))
    centroid = tuple((a[i] + b[i] + c[i]) / 3 for i in range(3))
    return area, angle, centroid, set(tri.vertices)


def _clusters(mesh, faces):
    remaining = set(faces)
    result = []
    while remaining:
        seed = min(remaining)
        remaining.remove(seed)
        group = {seed}
        queue = [seed]
        while queue:
            current = queue.pop()
            vertices = _face_data(mesh, current)[3]
            adjacent = sorted(
                face for face in remaining if len(vertices & _face_data(mesh, face)[3]) >= 2
            )
            for face in adjacent:
                remaining.remove(face)
                group.add(face)
                queue.append(face)
        result.append(tuple(sorted(group)))
    return tuple(result)


class SupportAnalyzer:
    def analyze(
        self,
        document: Universal3MFDocument,
        printability: PrintabilityReport,
        target: TargetProfile,
        mode: ConversionMode = ConversionMode.AUTOSLICE,
        minimum_confidence: Confidence = Confidence.HIGH,
    ) -> SupportPlan:
        del minimum_confidence
        required = []
        optional = []
        blocked = []
        diagnostics = []
        source_blockers = {
            r.target_object_id for r in document.supports.regions if "block" in r.kind.lower()
        }
        source_enforcers = {
            r.target_object_id for r in document.supports.regions if "enforc" in r.kind.lower()
        }
        source_blockers |= {
            o.object_id for o in document.objects if o.role is ObjectRole.SUPPORT_BLOCKER
        }
        source_enforcers |= {
            o.object_id for o in document.objects if o.role is ObjectRole.SUPPORT_ENFORCER
        }
        printable = {item.object_id: item for item in printability.objects}
        for obj in sorted(document.objects, key=lambda item: item.object_id):
            if not obj.mesh or obj.object_id not in printable:
                continue
            report = printable[obj.object_id]
            faces = tuple(
                sorted(set(report.overhangs.moderate_faces + report.overhangs.critical_faces))
            )
            if obj.object_id in source_enforcers and not faces:
                faces = tuple(range(min(1, len(obj.mesh.triangles))))
            for number, group in enumerate(_clusters(obj.mesh, faces), 1):
                data = [_face_data(obj.mesh, index) for index in group]
                area = sum(x[0] for x in data)
                centroid = tuple(
                    sum(x[2][i] * x[0] for x in data) / max(area, 1e-9) for i in range(3)
                )
                angle = sum(x[1] * x[0] for x in data) / max(area, 1e-9)
                enforced = obj.object_id in source_enforcers
                is_blocked = obj.object_id in source_blockers
                severity = (
                    "critical"
                    if any(face in report.overhangs.critical_faces for face in group)
                    else "moderate"
                )
                confidence = (
                    Confidence.HIGH if severity == "critical" or enforced else Confidence.MEDIUM
                )
                region = SupportRegion(
                    f"{obj.object_id}:{number}",
                    obj.object_id,
                    group,
                    round(area, 4),
                    round(angle, 2),
                    severity,
                    centroid[2] > 0.5,
                    "required" if severity == "critical" or enforced else "optional",
                    confidence,
                    tuple(round(v, 4) for v in centroid),
                    is_blocked,
                    enforced,
                )
                if is_blocked:
                    blocked.append(region)
                    diagnostics.append(
                        SupportDiagnostic(
                            "SUPPORT_CONFLICT",
                            f"Source blocker overlaps support region {region.region_id}.",
                        )
                    )
                elif region.requirement == "required":
                    required.append(region)
                else:
                    optional.append(region)
        supported = tuple(value.lower() for value in target.printer.support_types)
        if required:
            strategy = (
                SupportStrategy.TREE
                if "tree" in supported
                else (SupportStrategy.NORMAL if "normal" in supported else SupportStrategy.NONE)
            )
        elif optional:
            strategy = (
                SupportStrategy.BUILD_PLATE_ONLY
                if "build_plate_only" in supported
                else (SupportStrategy.NORMAL if "normal" in supported else SupportStrategy.NONE)
            )
        else:
            strategy = SupportStrategy.NONE
        if (required or optional) and strategy is SupportStrategy.NONE:
            diagnostics.append(
                SupportDiagnostic(
                    "SUPPORT_UNSUPPORTED", "Target provides no supported support strategy."
                )
            )
        elif required:
            diagnostics.append(
                SupportDiagnostic(
                    "SUPPORT_REQUIRED", f"Supports required for {len(required)} region(s)."
                )
            )
        elif optional:
            diagnostics.append(
                SupportDiagnostic(
                    "SUPPORT_RECOMMENDED", f"Supports recommended for {len(optional)} region(s)."
                )
            )
        else:
            diagnostics.append(
                SupportDiagnostic(
                    "SUPPORT_NOT_REQUIRED", "No unsupported overhang regions detected."
                )
            )
        all_active = required + optional
        estimated = (
            sum(r.area_mm2 * r.centroid_mm[2] * 0.15 for r in all_active) if all_active else 0.0
        )
        confidence = (
            Confidence.HIGH
            if required and all(r.confidence is Confidence.HIGH for r in required)
            else (Confidence.MEDIUM if all_active else Confidence.HIGH)
        )
        applied = (
            mode is ConversionMode.AUTOSLICE
            and bool(required)
            and confidence is Confidence.HIGH
            and strategy is not SupportStrategy.NONE
            and not blocked
        )
        return SupportPlan(
            strategy,
            tuple(required),
            tuple(optional),
            tuple(blocked),
            round(estimated, 2),
            confidence,
            tuple(diagnostics),
            applied,
            True,
        )
