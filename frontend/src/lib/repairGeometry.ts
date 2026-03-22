import * as THREE from "three";
import { mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";

export function repairGeometry(
  inputGeometry: THREE.BufferGeometry,
): THREE.BufferGeometry {
  let geometry = inputGeometry.clone();

  // Ensure geometry is indexed
  if (!geometry.index) {
    geometry = mergeVertices(geometry, 1e-5);
  }

  // Remove unsupported attributes (keeps only position, normal, uv)
  const allowed = ["position", "normal", "uv"];
  Object.keys(geometry.attributes).forEach((key) => {
    if (!allowed.includes(key)) {
      geometry.deleteAttribute(key);
    }
  });

  // Merge duplicate vertices
  geometry = mergeVertices(geometry, 1e-5);

  // Compute bounds
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();

  // Recalculate normals
  geometry.computeVertexNormals();

  // Mark attributes dirty
  geometry.attributes.position.needsUpdate = true;
  if (geometry.attributes.normal) {
    geometry.attributes.normal.needsUpdate = true;
  }

  return geometry;
}
