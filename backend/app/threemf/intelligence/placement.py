"""Deterministic build-plate analysis and bounded packing heuristics."""

from dataclasses import dataclass

from app.threemf.domain.document import Universal3MFDocument
from app.threemf.domain.settings import ConversionMode
from app.threemf.intelligence.models import Confidence, TargetProfile


@dataclass(frozen=True)
class PlacementDiagnostic:
    code: str
    message: str
    object_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObjectPlacement:
    item_index: int
    object_id: str
    plate_id: str
    transform: tuple[float, ...]
    bounding_box_mm: tuple[tuple[float, float, float], tuple[float, float, float]]


@dataclass(frozen=True)
class PlateAssignment:
    plate_id: str
    object_ids: tuple[str, ...]


@dataclass(frozen=True)
class PlacementCandidate:
    strategy: str
    placements: tuple[ObjectPlacement, ...]
    fits_build_volume: bool
    collision_count: int
    insufficient_spacing_count: int | None
    plate_utilization_percent: float
    score_breakdown: tuple[tuple[str, float], ...]
    score: float


@dataclass(frozen=True)
class PlacementPlan:
    current: PlacementCandidate
    recommended: PlacementCandidate
    candidates: tuple[PlacementCandidate, ...]
    plate_assignments: tuple[PlateAssignment, ...]
    diagnostics: tuple[PlacementDiagnostic, ...]
    confidence: Confidence
    applied: bool
    reanalysis_required: bool


def _apply(vertex, values):
    x, y, z = vertex
    return (
        values[0] * x + values[1] * y + values[2] * z + values[9],
        values[3] * x + values[4] * y + values[5] * z + values[10],
        values[6] * x + values[7] * y + values[8] * z + values[11],
    )


def _bounds(mesh, transform):
    points = tuple(_apply(v, transform) for v in mesh.vertices)
    return (
        tuple(min(v[i] for v in points) for i in range(3)),
        tuple(max(v[i] for v in points) for i in range(3)),
    )


def _overlap(a, b, spacing=0.0):
    return all(a[0][i] < b[1][i] + spacing and b[0][i] < a[1][i] + spacing for i in range(2))


class PlacementAnalyzer:
    def analyze(
        self,
        document: Universal3MFDocument,
        target: TargetProfile,
        mode: ConversionMode = ConversionMode.AUTOSLICE,
    ) -> PlacementPlan:
        objects = {obj.object_id: obj for obj in document.objects if obj.mesh and obj.mesh.vertices}
        items = tuple(
            (index, item)
            for index, item in enumerate(document.build.items)
            if item.object_id in objects
        )
        current = self._candidate("current", items, objects, target, None)
        diagnostics = []
        if not current.fits_build_volume:
            diagnostics.append(
                PlacementDiagnostic(
                    "OUTSIDE_BUILD_PLATE",
                    "One or more objects are outside the target build volume.",
                )
            )
        if current.collision_count:
            diagnostics.append(
                PlacementDiagnostic(
                    "OBJECT_COLLISION",
                    f"{current.collision_count} object bounding-box collision(s) detected.",
                )
            )
        if current.insufficient_spacing_count:
            diagnostics.append(
                PlacementDiagnostic(
                    "INSUFFICIENT_SPACING",
                    f"{current.insufficient_spacing_count} object pair(s) violate profile spacing.",
                )
            )
        if current.plate_utilization_percent < 10 and len(items) > 1:
            diagnostics.append(
                PlacementDiagnostic(
                    "UNNECESSARY_EMPTY_SPACE",
                    "Objects use less than 10% of the available plate envelope.",
                )
            )
        if len(document.build.plates) > 1:
            diagnostics.append(
                PlacementDiagnostic(
                    "MULTIPLE_PLATES_PRESERVED", "Automatic cross-plate packing is not enabled."
                )
            )
        candidates = [current]
        if items and len(document.build.plates) <= 1:
            for strategy in ("row", "shelf", "grid"):
                candidates.append(self._candidate(strategy, items, objects, target, strategy))
        ranked = sorted(candidates, key=lambda c: (-c.score, c.strategy))
        best = ranked[0]
        improvement = best.score - current.score
        gap = best.score - ranked[1].score if len(ranked) > 1 else 0
        confidence = (
            Confidence.HIGH
            if gap >= 5 and improvement >= 5
            else (Confidence.MEDIUM if improvement >= 2 else Confidence.LOW)
        )
        needs_change = bool(
            current.collision_count
            or not current.fits_build_volume
            or current.insufficient_spacing_count
        )
        applied = (
            mode is ConversionMode.AUTOSLICE
            and best.strategy != "current"
            and best.fits_build_volume
            and not best.collision_count
            and not best.insufficient_spacing_count
            and (needs_change or improvement >= 5)
            and len(document.build.plates) <= 1
        )
        assignments = tuple(
            PlateAssignment(
                plate.plate_id,
                tuple(
                    document.build.items[i].object_id
                    for i in plate.build_item_indices
                    if i < len(document.build.items)
                ),
            )
            for plate in document.build.plates
        ) or (PlateAssignment("default", tuple(item.object_id for _, item in items)),)
        return PlacementPlan(
            current,
            best,
            tuple(ranked),
            assignments,
            tuple(diagnostics),
            confidence,
            applied,
            applied,
        )

    def _candidate(self, strategy, items, objects, target, packing):
        spacing = target.printer.minimum_object_spacing_mm or 0.0
        width, depth, _height = target.printer.build_volume_mm
        placements = []
        cursor_x = cursor_y = row_height = 0.0
        columns = max(1, int(len(items) ** 0.5))
        for order, (index, item) in enumerate(items):
            obj = objects[item.object_id]
            base = list(item.transform.values)
            zero = tuple(base[:9] + [0.0, 0.0, 0.0])
            local = _bounds(obj.mesh, zero)
            dims = tuple(local[1][i] - local[0][i] for i in range(3))
            if packing == "row":
                x, y = cursor_x, 0.0
                cursor_x += dims[0] + spacing
            elif packing == "grid":
                x = (order % columns) * (dims[0] + spacing)
                y = (order // columns) * (dims[1] + spacing)
            elif packing == "shelf":
                if cursor_x and cursor_x + dims[0] > width:
                    cursor_x = 0.0
                    cursor_y += row_height + spacing
                    row_height = 0.0
                x, y = cursor_x, cursor_y
                cursor_x += dims[0] + spacing
                row_height = max(row_height, dims[1])
            else:
                x, y = base[9], base[10]
            if packing:
                base[9], base[10], base[11] = x - local[0][0], y - local[0][1], -local[0][2]
            bounds = _bounds(obj.mesh, tuple(base))
            placements.append(
                ObjectPlacement(
                    index, item.object_id, item.plate_id or "default", tuple(base), bounds
                )
            )
        collisions = spacing_violations = 0
        for i, a in enumerate(placements):
            for b in placements[i + 1 :]:
                if _overlap(a.bounding_box_mm, b.bounding_box_mm):
                    collisions += 1
                elif target.printer.minimum_object_spacing_mm is not None and _overlap(
                    a.bounding_box_mm, b.bounding_box_mm, spacing
                ):
                    spacing_violations += 1
        fit = all(
            p.bounding_box_mm[0][i] >= -1e-6
            and p.bounding_box_mm[1][i] <= target.printer.build_volume_mm[i] + 1e-6
            for p in placements
            for i in range(3)
        )
        if placements:
            minx = min(p.bounding_box_mm[0][0] for p in placements)
            maxx = max(p.bounding_box_mm[1][0] for p in placements)
            miny = min(p.bounding_box_mm[0][1] for p in placements)
            maxy = max(p.bounding_box_mm[1][1] for p in placements)
            utilization = 100 * (maxx - minx) * (maxy - miny) / (width * depth)
        else:
            utilization = 0.0
        fit_score = 100.0 if fit else 0.0
        collision_score = max(0.0, 100.0 - 50 * collisions)
        spacing_score = (
            100.0
            if target.printer.minimum_object_spacing_mm is None
            else max(0.0, 100.0 - 30 * spacing_violations)
        )
        utilization_score = max(0.0, 100.0 - abs(55.0 - min(utilization, 100.0)))
        support_score = 100.0
        orientation_score = 100.0
        score = (
            0.35 * fit_score
            + 0.3 * collision_score
            + 0.15 * spacing_score
            + 0.1 * utilization_score
            + 0.05 * support_score
            + 0.05 * orientation_score
        )
        return PlacementCandidate(
            strategy,
            tuple(placements),
            fit,
            collisions,
            None if target.printer.minimum_object_spacing_mm is None else spacing_violations,
            round(utilization, 2),
            (
                ("fit", fit_score),
                ("collision", collision_score),
                ("spacing", spacing_score),
                ("utilization", round(utilization_score, 2)),
                ("support", support_score),
                ("orientation", orientation_score),
            ),
            round(score, 2),
        )
