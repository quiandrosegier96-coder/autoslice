"""
AutoSlice — Mesh loader.
Converts a RawMeshObject into a trimesh.Trimesh for analysis.
"""

import numpy as np
import trimesh

from app.parser.model_parser import RawMeshObject


def load_mesh(obj: RawMeshObject) -> trimesh.Trimesh:
    """
    Build a trimesh.Trimesh from raw vertex and triangle data.
    """
    vertices = np.array(obj.vertices, dtype=np.float64)
    faces = np.array(obj.triangles, dtype=np.int64)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=True)


def merge_meshes(objects: list[RawMeshObject]) -> trimesh.Trimesh:
    """
    Merge all mesh objects into a single trimesh for whole-model analysis.
    """
    if not objects:
        raise ValueError("No mesh objects to merge.")
    if len(objects) == 1:
        return load_mesh(objects[0])
    meshes = [load_mesh(obj) for obj in objects]
    return trimesh.util.concatenate(meshes)
