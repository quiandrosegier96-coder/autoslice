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

    return GeometryAnalysis(
        bounding_box=bbox,
        part_count=len(parsed_model.objects),
        mesh_is_watertight=bool(mesh.is_watertight),
        estimated_volume_cm3=bbox.volume_cm3,
        overhang=overhang,
        bridge=bridge,
        thin_wall=thin_wall,
        surface_area_mm2=surface_area_mm2,
        contact_area_mm2=contact_area_mm2,
        height_to_base_ratio=height_to_base_ratio,
    )


def _safe(fn, mesh, fallback):
    """Run a geometry check and return fallback if it raises."""
    try:
        return fn(mesh)
    except Exception:
        return fallback
