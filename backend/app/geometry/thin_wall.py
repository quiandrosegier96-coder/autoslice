"""
AutoSlice — Thin wall / fragile structure detection.

Strategy:
  1. Fast SA/V ratio check — high ratio = likely thin walls
  2. If SA/V suggests thin walls, confirm with bilateral ray-cast:
     sample N points on surface, cast inward rays, measure exit distance.
     min_thickness = 5th percentile of measured distances.

SA/V intuition:
  Solid 10mm cube:    SA=600mm², V=1000mm³ → SA/V=0.6   → thick
  1mm × 50mm × 50mm: SA≈5100mm², V=2500mm³ → SA/V=2.04  → thin
  2mm × 30mm × 30mm: SA≈1920mm², V=1800mm³ → SA/V=1.07  → borderline
"""

import numpy as np
import trimesh

from app.models.geometry import ThinWallReport

DEFAULT_NOZZLE_DIAMETER_MM = 0.4
_SA_V_THIN_THRESHOLD = 0.9      # above this: suspected thin walls
_RAY_SAMPLE_COUNT = 250         # number of surface samples for ray-cast
_THIN_WALL_PERCENTILE = 5       # use 5th percentile to get minimum typical thickness


def detect_thin_walls(
    mesh: trimesh.Trimesh,
    nozzle_diameter_mm: float = DEFAULT_NOZZLE_DIAMETER_MM,
) -> ThinWallReport:
    """
    Estimate minimum wall thickness using SA/V heuristic + optional ray-cast.
    """
    total_area = float(mesh.area)
    volume = abs(float(mesh.volume))

    # Degenerate mesh guard
    if volume < 0.001 or total_area < 1.0:
        return ThinWallReport(has_thin_walls=True, min_thickness_mm=nozzle_diameter_mm)

    sa_v_ratio = total_area / volume  # 1/mm units

    # Estimate average wall thickness from SA/V
    # For a flat sheet of thickness t: SA/V ≈ 2/t (dominant faces)
    estimated_thickness_mm = round(2.0 / max(sa_v_ratio, 0.01), 3)

    # If SA/V is low, walls are definitely thick — skip expensive ray-cast
    if sa_v_ratio < _SA_V_THIN_THRESHOLD:
        return ThinWallReport(has_thin_walls=False, min_thickness_mm=estimated_thickness_mm)

    # SA/V suggests thin walls — confirm with ray-cast
    min_thickness = _ray_cast_thickness(mesh, nozzle_diameter_mm)

    if min_thickness is None:
        # Ray-cast failed — use SA/V estimate
        thin = estimated_thickness_mm < nozzle_diameter_mm * 2.0
        return ThinWallReport(has_thin_walls=thin, min_thickness_mm=estimated_thickness_mm)

    has_thin = min_thickness < nozzle_diameter_mm * 2.0
    return ThinWallReport(has_thin_walls=has_thin, min_thickness_mm=min_thickness)


def _ray_cast_thickness(mesh: trimesh.Trimesh, nozzle_mm: float) -> float | None:
    """
    Sample surface points and cast inward rays to measure wall thickness.
    Returns 5th-percentile thickness, or None if ray-cast fails.
    """
    try:
        n_samples = min(_RAY_SAMPLE_COUNT, max(50, len(mesh.faces) // 10))
        points, face_indices = trimesh.sample.sample_surface(mesh, count=n_samples)
        face_normals = mesh.face_normals[face_indices]  # (N, 3)

        # Offset start points slightly inside the mesh (0.05mm inward)
        ray_origins = points - face_normals * 0.05
        ray_directions = -face_normals

        locs, ray_idx, _ = mesh.ray.intersects_location(
            ray_origins=ray_origins,
            ray_directions=ray_directions,
            multiple_hits=False,
        )

        if len(locs) == 0:
            return None

        # Distance from origin to exit point
        dists = np.linalg.norm(locs - ray_origins[ray_idx], axis=1)

        # Filter out near-zero (self-intersections) and extreme values
        valid = dists[(dists > 0.05) & (dists < 200.0)]
        if len(valid) == 0:
            return None

        min_thickness = round(float(np.percentile(valid, _THIN_WALL_PERCENTILE)), 3)
        return max(0.1, min_thickness)

    except Exception:
        return None
