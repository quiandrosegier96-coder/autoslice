/**
 * AutoSlice — Branch collision avoider (v2).
 *
 * Uses Three.js Raycaster to detect when a tree branch intersects the source
 * mesh, and inserts waypoint nodes to steer around the collision.
 *
 * Strategy
 * ────────
 * Pre-pass:
 *   For every non-root node check if the node is already inside the mesh using
 *   the ray-parity (even-odd) rule.  If so, push it out along the nearest
 *   surface normal.
 *
 * Per-segment:
 *   1. Cast a ray from start → end along the segment direction.
 *   2. If a hit is found within the segment length:
 *      a. Compute a waypoint at the hit point pushed along the outward surface
 *         normal by (collisionMarginMm × 3).
 *      b. Clamp waypoint Y to the segment Y range so we stay below the model.
 *      c. Insert the waypoint node and two replacement segments.
 *   3. Repeat up to MAX_ITERS times per segment.
 */

import * as THREE from "three";
import type { TreeNode, TreeSegment, GraphResult, SupportConfig } from "./types";

const MAX_ITERS    = 8;
const HIT_EPSILON  = 0.3;   // mm — ignore hits this close to ray origin
const PARITY_DIRS: THREE.Vector3[] = [
  new THREE.Vector3( 0,  1,  0),
  new THREE.Vector3( 1,  0,  0),
  new THREE.Vector3( 0,  0,  1),
];

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Ray-parity inside-mesh test.
 * Casts rays in PARITY_DIRS and counts how many directions yield an odd number
 * of hits.  If the majority is odd the point is inside the mesh.
 */
function isInsideMesh(
  point:     THREE.Vector3,
  meshes:    THREE.Mesh[],
  raycaster: THREE.Raycaster,
): boolean {
  const saved = raycaster.firstHitOnly;
  raycaster.firstHitOnly = false;
  let votes = 0;
  for (const dir of PARITY_DIRS) {
    raycaster.set(point, dir);
    const hits = raycaster.intersectObjects(meshes, false);
    if ((hits.length & 1) === 1) votes++;
  }
  raycaster.firstHitOnly = saved;
  return votes >= 2;
}

/**
 * Convert a face normal (object-space) to world-space.
 * Returns a unit vector pointing away from the mesh surface.
 */
function toWorldNormal(face: THREE.Face, mesh: THREE.Mesh): THREE.Vector3 {
  const nm = new THREE.Matrix3().getNormalMatrix(mesh.matrixWorld);
  return face.normal.clone().applyMatrix3(nm).normalize();
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Mutate the GraphResult in-place: insert waypoints wherever branches
 * intersect the model.
 *
 * @param result       Graph to modify (nodes + segments).
 * @param targetObject Root Object3D of the model (multi-mesh safe).
 * @param config       Support config — uses collisionMarginMm.
 */
export function avoidCollisions(
  result:       GraphResult,
  targetObject: THREE.Object3D,
  config:       SupportConfig,
): void {
  // Collect every mesh
  const meshes: THREE.Mesh[] = [];
  targetObject.traverse((child) => {
    if ((child as THREE.Mesh).isMesh) meshes.push(child as THREE.Mesh);
  });
  if (meshes.length === 0) return;

  const margin = Math.max(config.collisionMarginMm * 3.0, 2.0);

  const raycaster = new THREE.Raycaster();
  raycaster.firstHitOnly = true;

  // ── Pre-pass: push nodes that are already inside the mesh outside ──────────
  for (const node of result.nodes.values()) {
    if (node.type === "root") continue;   // build-plate root is always safe
    if (!isInsideMesh(node.position, meshes, raycaster)) continue;

    // Find the nearest exit point by casting in +Y
    raycaster.firstHitOnly = true;
    raycaster.set(node.position, new THREE.Vector3(0, 1, 0));
    const hits = raycaster.intersectObjects(meshes, false);
    if (hits.length > 0) {
      const h = hits[0];
      if (h.face) {
        let wn = toWorldNormal(h.face, h.object as THREE.Mesh);
        // Ensure normal points outward (away from interior)
        if (wn.y < 0) wn = wn.negate();
        node.position.copy(h.point).addScaledVector(wn, margin);
      } else {
        node.position.y = h.point.y + margin;
      }
    } else {
      // Fallback: nudge downward below the model
      node.position.y -= margin * 2;
    }
  }

  // ── Per-segment pass ───────────────────────────────────────────────────────
  let nextNodeId = Math.max(...result.nodes.keys()) + 1;
  let nextSegId  = result.segments.reduce(
    (m: number, s: TreeSegment) => Math.max(m, s.id), 0,
  ) + 1;

  // Snapshot — we'll mutate result.segments during the loop
  const originalSegments = [...result.segments];

  for (const seg of originalSegments) {
    avoidSegment(seg, result, meshes, raycaster, margin, nextNodeId, nextSegId);
    // Recompute id counters after possible insertions
    nextNodeId = Math.max(...result.nodes.keys()) + 1;
    nextSegId  = result.segments.reduce(
      (m: number, s: TreeSegment) => Math.max(m, s.id), 0,
    ) + 1;
  }
}

// ── Internal segment fixer ────────────────────────────────────────────────────

function avoidSegment(
  seg:        TreeSegment,
  result:     GraphResult,
  meshes:     THREE.Mesh[],
  raycaster:  THREE.Raycaster,
  margin:     number,
  nextNodeId: number,
  nextSegId:  number,
): void {
  raycaster.firstHitOnly = true;

  for (let iter = 0; iter < MAX_ITERS; iter++) {
    const a = result.nodes.get(seg.startNodeId);
    const b = result.nodes.get(seg.endNodeId);
    if (!a || !b) return;

    const dir = b.position.clone().sub(a.position);
    const len = dir.length();
    if (len < 1e-6) return;
    dir.divideScalar(len);

    raycaster.set(a.position, dir);
    const hits = raycaster.intersectObjects(meshes, false);
    if (hits.length === 0) return;

    const hit = hits[0];
    // Skip hits at the very start (rounding) or at/past the endpoint
    if (hit.distance < HIT_EPSILON || hit.distance > len - HIT_EPSILON) return;

    // ── Determine push direction from surface normal ──────────────────────
    let pushDir: THREE.Vector3;
    if (hit.face) {
      pushDir = toWorldNormal(hit.face, hit.object as THREE.Mesh);
      // If normal faces the same direction as the ray, we hit a back face —
      // flip it so we always push outward (away from mesh interior).
      if (pushDir.dot(dir) > 0) pushDir.negate();
    } else {
      // Fallback: push perpendicular to segment, horizontal plane
      pushDir = new THREE.Vector3(-dir.z, 0, dir.x).normalize();
    }

    // ── Waypoint position ─────────────────────────────────────────────────
    const wPos = hit.point.clone().addScaledVector(pushDir, margin);

    // Clamp Y to the segment Y range so the waypoint stays below the model
    const lo = Math.min(a.position.y, b.position.y);
    const hi = Math.max(a.position.y, b.position.y);
    wPos.y = Math.max(lo, Math.min(hi, wPos.y));

    // ── Insert waypoint node ──────────────────────────────────────────────
    const rMid: number = (seg.radiusStart + seg.radiusEnd) * 0.5;
    const waypoint: TreeNode = {
      id:       nextNodeId++,
      position: wPos,
      radius:   rMid,
      parentId: a.id,
      childIds: [b.id],
      type:     "waypoint",
    };
    result.nodes.set(waypoint.id, waypoint);
    a.childIds = a.childIds.map((id: number) => (id === b.id ? waypoint.id : id));
    b.parentId = waypoint.id;

    // ── Replace original segment with two sub-segments ───────────────────
    const segA: TreeSegment = {
      id:          nextSegId++,
      startNodeId: a.id,
      endNodeId:   waypoint.id,
      radiusStart: seg.radiusStart,
      radiusEnd:   rMid,
    };
    const segB: TreeSegment = {
      id:          nextSegId++,
      startNodeId: waypoint.id,
      endNodeId:   b.id,
      radiusStart: rMid,
      radiusEnd:   seg.radiusEnd,
    };
    const idx = result.segments.indexOf(seg);
    if (idx >= 0) {
      result.segments.splice(idx, 1, segA, segB);
    } else {
      result.segments.push(segA, segB);
    }

    // Continue checking the second sub-segment
    seg = segB;
  }
}
