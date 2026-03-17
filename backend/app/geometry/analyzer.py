"""
AutoSlice — Geometry analysis orchestrator.
Coordinates all geometry checks and returns a GeometryAnalysis result.
"""

import trimesh

from app.models.geometry import GeometryAnalysis, BoundingBox, OverhangReport, BridgeReport, ThinWallReport
from app.parser.model_parser import ParsedModel
from app.geometry.mesh_loader import merge_meshes
from app.geometry.bounding_box import compute_bounding_box
from app.geometry.overhang import detect_overhangs
from app.geometry.bridge import detect_bridges
from app.geometry.thin_wall import detect_thin_walls
from app.geometry.contact_area import compute_contact_metrics


def analyze(parsed_model: ParsedModel) -> GeometryAnalysis:
    """
    Run all geometry analysis passes on the parsed model.
    Merges all mesh objects, then runs bounding box, overhang,
    bridge, thin-wall, contact area, and stability checks.
    Falls back to safe defaults if any individual check fails.
    """
    if not parsed_model.objects:
        raise ValueError("3MF model contains no mesh objects.")

    try:
        mesh: trimesh.Trimesh = merge_meshes(parsed_model.objects)
    except Exception as exc:
        raise ValueError(f"Failed to load mesh geometry: {exc}") from exc

    return analyze_mesh(mesh, len(parsed_model.objects))


def analyze_mesh(mesh: trimesh.Trimesh, part_count: int = 1) -> GeometryAnalysis:
    """
    Run all geometry analysis passes on an already-loaded trimesh.
    Allows callers that have already built the mesh (e.g. orientation scorer)
    to avoid a second merge_meshes call.
    """
    bbox = _safe(compute_bounding_box, mesh, BoundingBox(0.0, 0.0, 0.0, 0.0))
    overhang = _safe(detect_overhangs, mesh, OverhangReport(False, 0.0, 0.0))
    bridge = _safe(detect_bridges, mesh, BridgeReport(False, 0.0))
    thin_wall = _safe(detect_thin_walls, mesh, ThinWallReport(False, 999.0))

    # Surface area (mm²)
    try:
        surface_area_mm2 = round(float(mesh.area), 2)
    except Exception:
        surface_area_mm2 = 0.0

    # Contact area and height-to-base ratio
    contact_area_mm2, height_to_base_ratio = 0.0, 0.0
    try:
        contact_area_mm2, height_to_base_ratio = compute_contact_metrics(mesh)
    except Exception:
        pass

    # Slenderness ratio: z / min(x, y) — raw aspect ratio (independent of contact area)
    slenderness_ratio = 0.0
    try:
        min_xy = min(bbox.x_mm, bbox.y_mm)
        if min_xy > 0:
            slenderness_ratio = round(bbox.z_mm / min_xy, 4)
    except Exception:
        pass

    # Center-of-mass Z ratio: CoM_z / height (0=bottom, 1=top; >0.6 = top-heavy)
    center_of_mass_z_ratio = 0.5
    try:
        com = mesh.center_mass   # [x, y, z]
        height = bbox.z_mm
        if height > 0:
            min_z = float(mesh.bounds[0][2])
            center_of_mass_z_ratio = round((float(com[2]) - min_z) / height, 4)
            center_of_mass_z_ratio = max(0.0, min(1.0, center_of_mass_z_ratio))
    except Exception:
        pass

    return GeometryAnalysis(
        bounding_box=bbox,
        part_count=part_count,
        mesh_is_watertight=bool(mesh.is_watertight),
        estimated_volume_cm3=bbox.volume_cm3,
        overhang=overhang,
        bridge=bridge,
        thin_wall=thin_wall,
        surface_area_mm2=surface_area_mm2,
        contact_area_mm2=contact_area_mm2,
        height_to_base_ratio=height_to_base_ratio,
        slenderness_ratio=slenderness_ratio,
        center_of_mass_z_ratio=center_of_mass_z_ratio,
    )


def _safe(fn, mesh, fallback):
    """Run a geometry check and return fallback if it raises."""
    try:
        return fn(mesh)
    except Exception:
        return fallback
