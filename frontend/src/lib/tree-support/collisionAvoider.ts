/**
 * AutoSlice — Branch collision avoider.
 *
 * Uses Three.js Raycaster to detect when a tree branch intersects the source
 * mesh, and inserts waypoint nodes to steer around the collision.
 *
 * Strategy
 * ────────
 * For each segment (parent → child):
 *   1. Cast a ray along the segment direction.
 *   2. If a hit is found within the segment length (minus a small epsilon):
 *      a. Compute a waypoint at the hit point pushed outward from the mesh
 *         bounding-box centre, offset by collisionMarginMm * 3.
 *      b. Clamp waypoint Y between parent.y and child.y.
 *      c. Insert the waypoint node and two replacement segments.
 *   3. Repeat up to MAX_ITERS times per segment (handles concave shapes).
 */

import * as THREE from "three";
import type { TreeNode, TreeSegment, GraphResult, SupportConfig } from "./types";

const MAX_ITERS   = 3;
const HIT_EPSILON = 0.5;   // mm — ignore hits closer than this to the ray origin

/**
 * Mutate the GraphResult in-place: insert waypoints wherever branches
 * intersect `targetMesh`.
 *
 * @param result      Graph to modify (nodes + segments).
 * @param targetMesh  The mesh to avoid (THREE.Mesh, must have geometry).
 * @param config      Support config — uses collisionMarginMm.
 */
export function avoidCollisions(
  result:     GraphResult,
  targetMesh: THREE.Mesh,
  config:     SupportConfig,
): void {
  const margin = config.collisionMarginMm * 3.0;

  // Bounding sphere centre — used as "outward" reference direction
  const bbox   = new THREE.Box3().setFromObject(targetMesh);
  const centre = bbox.getCenter(new THREE.Vector3());

  const raycaster = new THREE.Raycaster();
  raycaster.firstHitOnly = true;

  let nextNodeId = Math.max(...result.nodes.keys()) + 1;
  let nextSegId  = result.segments.length;

  // We work on a snapshot of segments because we mutate the array
  const originalSegments = [...result.segments];

  for (const seg of originalSegments) {
    avoidSegment(seg, result, targetMesh, raycaster, centre, margin,
      nextNodeId, nextSegId, config);
    // Recompute next ids after possible insertions
    nextNodeId = Math.max(...result.nodes.keys()) + 1;
    nextSegId  = result.segments.reduce((m: number, s: TreeSegment) => Math.max(m, s.id), 0) + 1;
  }
}

function avoidSegment(
  seg:        TreeSegment,
  result:     GraphResult,
  mesh:       THREE.Mesh,
  raycaster:  THREE.Raycaster,
  centre:     THREE.Vector3,
  margin:     number,
  nextNodeId: number,
  nextSegId:  number,
  _config:    SupportConfig,
): void {
  for (let iter = 0; iter < MAX_ITERS; iter++) {
    const a = result.nodes.get(seg.startNodeId);
    const b = result.nodes.get(seg.endNodeId);
    if (!a || !b) return;

    const dir  = b.position.clone().sub(a.position);
    const len  = dir.length();
    if (len < 1e-6) return;
    dir.divideScalar(len);

    raycaster.set(a.position, dir);
    const hits = raycaster.intersectObject(mesh, false);
    if (hits.length === 0) return;

    const hit = hits[0];
    if (hit.distance < HIT_EPSILON || hit.distance > len - HIT_EPSILON) return;

    // Outward direction from mesh centre to hit point (XZ only)
    const outward = new THREE.Vector3(
      hit.point.x - centre.x,
      0,
      hit.point.z - centre.z,
    ).normalize();
    if (outward.length() < 1e-6) outward.set(1, 0, 0);

    // Waypoint: hit point pushed outward, Y clamped to segment range
    const wY = Math.max(Math.min(hit.point.y, Math.max(a.position.y, b.position.y)),
                        Math.min(a.position.y, b.position.y));
    const wPos = new THREE.Vector3(
      hit.point.x + outward.x * margin,
      wY,
      hit.point.z + outward.z * margin,
    );

    // Create waypoint node
    const rMid = (seg.radiusStart + seg.radiusEnd) * 0.5;
    const waypoint: TreeNode = {
      id:       nextNodeId++,
      position: wPos,
      radius:   rMid,
      parentId: a.id,
      childIds: [b.id],
      type:     "waypoint",
    };
    result.nodes.set(waypoint.id, waypoint);
    a.childIds = a.childIds.map((id: number) => id === b.id ? waypoint.id : id);
    b.parentId = waypoint.id;

    // Replace original segment with two new segments
    const idx = result.segments.indexOf(seg);
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
    if (idx >= 0) {
      result.segments.splice(idx, 1, segA, segB);
    } else {
      result.segments.push(segA, segB);
    }

    // Continue checking the second sub-segment
    seg = segB;
  }
}
