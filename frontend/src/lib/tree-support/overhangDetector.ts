/**
 * AutoSlice — Overhang detector.
 *
 * Analyses every triangle in a Three.js BufferGeometry and marks faces whose
 * normal points sufficiently downward to require support.
 *
 * Coordinate space: Three.js Y-up world space.
 * Gravity direction: (0, -1, 0).
 * A face is an overhang when dot(faceNormal, gravity) > cos(overhangAngleDeg).
 */

import * as THREE from "three";
import type { OverhangFace } from "./types";

/** Gravity unit vector in Three.js Y-up space. */
const GRAVITY = new THREE.Vector3(0, -1, 0);

/**
 * Detect unsupported overhang faces in a mesh.
 *
 * @param geometry    Source BufferGeometry (may be indexed or non-indexed).
 * @param matrixWorld World transform of the mesh.
 * @param angleDeg    Overhang threshold in degrees (default 45).
 *                    Faces whose normal is within angleDeg of straight-down
 *                    are considered overhangs.
 * @param floorY      Faces at or below this Y are ignored (build-plate contact).
 */
export function detectOverhangs(
  geometry:    THREE.BufferGeometry,
  matrixWorld: THREE.Matrix4,
  angleDeg:    number = 45,
  floorY:      number = 0,
): OverhangFace[] {
  // A face is an overhang when the angle between its normal and the gravity
  // direction is LESS than angleDeg (the normal almost points straight down).
  // cos is a decreasing function, so:   dot > cos(angleDeg) → overhang.
  const cosThreshold = Math.cos(THREE.MathUtils.degToRad(angleDeg));

  const posAttr = geometry.attributes.position as THREE.BufferAttribute;
  const index   = geometry.index;
  const triCount = index ? index.count / 3 : posAttr.count / 3;

  // Reusable allocations
  const v0 = new THREE.Vector3();
  const v1 = new THREE.Vector3();
  const v2 = new THREE.Vector3();
  const e1 = new THREE.Vector3();
  const e2 = new THREE.Vector3();
  const n  = new THREE.Vector3();
  const c  = new THREE.Vector3();

  // Normal matrix — avoids non-uniform scale distortion
  const normalMatrix = new THREE.Matrix3().getNormalMatrix(matrixWorld);

  const results: OverhangFace[] = [];

  for (let i = 0; i < triCount; i++) {
    const a = index ? index.getX(i * 3)     : i * 3;
    const b = index ? index.getX(i * 3 + 1) : i * 3 + 1;
    const cc = index ? index.getX(i * 3 + 2) : i * 3 + 2;

    v0.fromBufferAttribute(posAttr, a).applyMatrix4(matrixWorld);
    v1.fromBufferAttribute(posAttr, b).applyMatrix4(matrixWorld);
    v2.fromBufferAttribute(posAttr, cc).applyMatrix4(matrixWorld);

    // Geometric face normal (not vertex normal) for accuracy
    e1.subVectors(v1, v0);
    e2.subVectors(v2, v0);
    n.crossVectors(e1, e2).normalize();
    // Apply normal matrix to handle non-uniform transforms
    n.applyMatrix3(normalMatrix).normalize();

    // dot(n, gravity) — how strongly does this face point downward?
    const dot = n.dot(GRAVITY);
    if (dot <= cosThreshold) continue;  // not an overhang

    // Centroid — skip faces on/near the build plate
    c.addVectors(v0, v1).add(v2).divideScalar(3);
    if (c.y <= floorY + 0.5) continue;

    // Triangle area (half of cross-product magnitude)
    const area = e1.clone().cross(e2).length() * 0.5;
    if (area < 0.01) continue;  // degenerate triangle

    results.push({
      index:      i,
      normal:     n.clone(),
      centroid:   c.clone(),
      vertices:   [v0.clone(), v1.clone(), v2.clone()],
      area,
      overhangDot: dot,
    });
  }

  return results;
}

/**
 * Collect geometry from a Three.js scene object (handles Groups / merged meshes).
 * Returns an array of { geometry, matrixWorld } pairs.
 */
export function collectGeometries(
  object: THREE.Object3D,
): Array<{ geometry: THREE.BufferGeometry; matrixWorld: THREE.Matrix4 }> {
  const result: Array<{ geometry: THREE.BufferGeometry; matrixWorld: THREE.Matrix4 }> = [];
  object.updateWorldMatrix(true, true);
  object.traverse((child) => {
    if ((child as THREE.Mesh).isMesh) {
      const mesh = child as THREE.Mesh;
      if (mesh.geometry) {
        result.push({ geometry: mesh.geometry, matrixWorld: mesh.matrixWorld.clone() });
      }
    }
  });
  return result;
}

/**
 * Compute the Y-axis floor position (lowest point of the bounding box).
 * Used to exclude build-plate-contact faces from overhang detection.
 */
export function computeFloorY(object: THREE.Object3D): number {
  const box = new THREE.Box3().setFromObject(object);
  return box.min.y;
}

/**
 * Remove overhang faces that are already supported by model geometry below.
 *
 * For each face, cast a ray straight down (-Y) from just below the centroid.
 * If the ray hits any part of the model before reaching plateY, the face is
 * self-supported → exclude it.  Only faces with clear air all the way to the
 * build plate truly need a support structure.
 *
 * @param faces       Overhang faces from detectOverhangs().
 * @param meshes      All mesh instances to cast against.
 * @param plateY      Build plate Y — rays that reach here indicate a support need.
 * @param selfEpsilon Offset below centroid to avoid self-intersection (mm).
 */
export function filterSupportedFaces(
  faces:       OverhangFace[],
  meshes:      THREE.Mesh[],
  plateY:      number,
  selfEpsilon: number = 0.4,
): OverhangFace[] {
  if (meshes.length === 0) return faces;

  const DOWN      = new THREE.Vector3(0, -1, 0);
  const raycaster = new THREE.Raycaster();
  raycaster.firstHitOnly = true;

  return faces.filter((face) => {
    // Start the ray slightly below the centroid to avoid hitting the face itself
    const origin   = face.centroid.clone();
    origin.y      -= selfEpsilon;
    const clearance = origin.y - plateY;

    // Face centroid is already at or below the plate — not a real overhang
    if (clearance <= 0) return false;

    raycaster.set(origin, DOWN);

    // Test against every mesh; stop as soon as we find a hit well above the plate
    for (const mesh of meshes) {
      const hits = raycaster.intersectObject(mesh, false);
      if (hits.length > 0 && hits[0].distance < clearance - selfEpsilon) {
        // Solid geometry exists below this face → already supported
        return false;
      }
    }

    // Nothing below → needs a support column
    return true;
  });
}
