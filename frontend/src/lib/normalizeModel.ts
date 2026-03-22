import * as THREE from "three";

export function normalizeModelOnBed(mesh: THREE.Mesh): THREE.Mesh {
  const geometry = mesh.geometry;
  geometry.computeBoundingBox();

  const box = geometry.boundingBox!;
  const center = new THREE.Vector3();
  box.getCenter(center);

  // Center X/Z, align bottom to Y = 0
  geometry.translate(-center.x, -box.min.y, -center.z);

  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();

  return mesh;
}
