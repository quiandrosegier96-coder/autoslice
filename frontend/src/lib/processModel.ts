import * as THREE from "three";
import { flattenModelToSingleGeometry } from "./flattenModel";
import { autoOrientGeometry }           from "./autoOrient";
import { normalizeModelOnBed }          from "./normalizeModel";

const MODEL_MATERIAL = new THREE.MeshStandardMaterial({
  color:     0xcc2222,
  roughness: 0.6,
  metalness: 0.1,
});

export type ProcessModelResult = {
  mesh:     THREE.Mesh;
  supports: THREE.Group | null;
};

/**
 * Flatten, orient and place a loaded scene onto the print bed.
 * Does NOT mutate any Three.js scene — caller renders declaratively.
 * Supports are not generated here — call generateBasicSupports() separately.
 */
export function processModel(
  loadedScene: THREE.Object3D,
): ProcessModelResult {
  let geometry = flattenModelToSingleGeometry(loadedScene);
  geometry     = autoOrientGeometry(geometry);

  const mesh = new THREE.Mesh(geometry, MODEL_MATERIAL.clone());
  normalizeModelOnBed(mesh);

  return { mesh, supports: null };
}
