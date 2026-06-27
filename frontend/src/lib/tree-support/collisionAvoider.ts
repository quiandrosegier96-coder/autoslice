/**
 * AutoSlice - tree support collision pruning.
 *
 * The preview must never draw green support members through the red model.
 * When a generated route intersects the model before its final contact point,
 * this module rejects that route instead of trying to bend it around the mesh.
 * That is closer to slicer behavior and avoids ugly sideways branches.
 */

import * as THREE from "three";
import type { GraphResult, SupportConfig } from "./types";

const HIT_EPSILON = 0.3;
const CONTACT_CLEARANCE_MM = 1.2;
const PARITY_DIRS: THREE.Vector3[] = [
  new THREE.Vector3(0, 1, 0),
  new THREE.Vector3(1, 0, 0),
  new THREE.Vector3(0, 0, 1),
];

function isInsideMesh(
  point: THREE.Vector3,
  meshes: THREE.Mesh[],
  raycaster: THREE.Raycaster,
): boolean {
  const savedFirstHitOnly = raycaster.firstHitOnly;
  const savedNear = raycaster.near;
  const savedFar = raycaster.far;

  raycaster.firstHitOnly = false;
  raycaster.near = 0.001;
  raycaster.far = Infinity;

  let votes = 0;
  for (const dir of PARITY_DIRS) {
    raycaster.set(point, dir);
    const hits = raycaster.intersectObjects(meshes, false);
    if ((hits.length & 1) === 1) votes++;
  }

  raycaster.firstHitOnly = savedFirstHitOnly;
  raycaster.near = savedNear;
  raycaster.far = savedFar;
  return votes >= 2;
}

function removeSubtree(result: GraphResult, nodeId: number): void {
  const stack = [nodeId];
  const removeIds = new Set<number>();

  while (stack.length > 0) {
    const id = stack.pop()!;
    if (removeIds.has(id)) continue;
    removeIds.add(id);
    const node = result.nodes.get(id);
    if (node) stack.push(...node.childIds);
  }

  for (const id of removeIds) result.nodes.delete(id);

  result.segments = result.segments.filter(
    (seg) => !removeIds.has(seg.startNodeId) && !removeIds.has(seg.endNodeId),
  );

  for (const node of result.nodes.values()) {
    node.childIds = node.childIds.filter((id) => !removeIds.has(id));
    if (node.parentId !== null && removeIds.has(node.parentId)) node.parentId = null;
  }
}

function firstSegmentHit(
  a: THREE.Vector3,
  b: THREE.Vector3,
  meshes: THREE.Mesh[],
  raycaster: THREE.Raycaster,
): THREE.Intersection | null {
  const dir = b.clone().sub(a);
  const len = dir.length();
  if (len < 1e-6) return null;

  const savedNear = raycaster.near;
  const savedFar = raycaster.far;
  const savedFirstHitOnly = raycaster.firstHitOnly;

  raycaster.firstHitOnly = true;
  raycaster.near = HIT_EPSILON;
  raycaster.far = Math.max(HIT_EPSILON, len - HIT_EPSILON);
  raycaster.set(a, dir.divideScalar(len));

  const hits = raycaster.intersectObjects(meshes, false);

  raycaster.near = savedNear;
  raycaster.far = savedFar;
  raycaster.firstHitOnly = savedFirstHitOnly;

  return hits.length > 0 ? hits[0] : null;
}

export function avoidCollisions(
  result: GraphResult,
  targetObject: THREE.Object3D,
  config: SupportConfig,
): void {
  const meshes: THREE.Mesh[] = [];
  targetObject.traverse((child) => {
    if ((child as THREE.Mesh).isMesh) meshes.push(child as THREE.Mesh);
  });
  if (meshes.length === 0) return;

  const margin = Math.max(config.collisionMarginMm * 3.0, 2.0);
  const raycaster = new THREE.Raycaster();

  const invalidNodeIds: number[] = [];
  for (const node of result.nodes.values()) {
    if (node.type === "root" || node.type === "contact") continue;
    if (isInsideMesh(node.position, meshes, raycaster)) invalidNodeIds.push(node.id);
  }

  for (const id of invalidNodeIds) {
    if (result.nodes.has(id)) removeSubtree(result, id);
  }

  for (const seg of [...result.segments]) {
    const a = result.nodes.get(seg.startNodeId);
    const b = result.nodes.get(seg.endNodeId);
    if (!a || !b) continue;

    const hit = firstSegmentHit(a.position, b.position, meshes, raycaster);
    if (!hit) continue;

    const len = a.position.distanceTo(b.position);
    const allowedContactTouch =
      b.type === "contact" && hit.distance >= len - Math.max(CONTACT_CLEARANCE_MM, margin * 0.5);

    if (!allowedContactTouch) removeSubtree(result, b.id);
  }
}
