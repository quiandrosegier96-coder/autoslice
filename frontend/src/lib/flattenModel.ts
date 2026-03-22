import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { repairGeometry } from "./repairGeometry";

export function flattenModelToSingleGeometry(
  root: THREE.Object3D,
): THREE.BufferGeometry {
  const geometries: THREE.BufferGeometry[] = [];

  root.updateMatrixWorld(true);

  root.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (mesh.isMesh && mesh.geometry) {
      let g = mesh.geometry.clone();

      // Bake world transform into vertex positions
      g.applyMatrix4(mesh.matrixWorld);

      // Repair each piece before merging
      g = repairGeometry(g);

      geometries.push(g);
    }
  });

  if (!geometries.length) {
    throw new Error("No mesh geometry found in upload.");
  }

  const merged = mergeGeometries(geometries, true);
  if (!merged) {
    throw new Error("Failed to merge geometries.");
  }

  return repairGeometry(merged);
}
