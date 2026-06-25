/**
 * AutoSlice — Support mesh builder.
 *
 * Converts a TreeSupportGraph (nodes + segments) into renderable Three.js
 * geometry:
 *
 *   - Each segment  → tapered CylinderGeometry (ConeGeometry when tip→contact)
 *   - Each tip node → SphereGeometry (small ball at contact point)
 *   - All meshes merged into a single THREE.Group for the support layer
 *
 * Colour scheme
 * ─────────────
 *   trunk / branch  →  #4a9eff  (blue)
 *   tip             →  #ff9f40  (amber)
 *   contact         →  #ff4f4f  (red)
 *   waypoint        →  #a0a0a0  (grey)
 */

import * as THREE from "three";
import type { TreeNode, TreeSegment, SupportConfig } from "./types";

// ── Materials (shared across all support instances) ────────────────────────────

const MAT_TRUNK = new THREE.MeshStandardMaterial({
  color: 0x55d88a, roughness: 0.72, metalness: 0.0,
  transparent: true, opacity: 0.88,
  side: THREE.DoubleSide,
});
const MAT_TIP = new THREE.MeshStandardMaterial({
  color: 0x6fe29c, roughness: 0.68, metalness: 0.0,
  transparent: true, opacity: 0.9,
});
const MAT_CONTACT = new THREE.MeshStandardMaterial({
  color: 0xffb454, roughness: 0.55, metalness: 0.0,
});
const MAT_WAYPOINT = new THREE.MeshStandardMaterial({
  color: 0x8fb9a0, roughness: 0.8, metalness: 0.0,
  transparent: true, opacity: 0.75,
});

const Y_AXIS = new THREE.Vector3(0, 1, 0);

function matFor(type: string): THREE.MeshStandardMaterial {
  if (type === "contact")                return MAT_CONTACT;
  if (type === "tip")                    return MAT_TIP;
  if (type === "waypoint")               return MAT_WAYPOINT;
  return MAT_TRUNK;
}

// ── Main builder ───────────────────────────────────────────────────────────────

/**
 * Build a THREE.Group containing all support geometry.
 *
 * @param nodes     Node map from buildGraph().
 * @param segments  Segment list from buildGraph().
 * @param config    Support config — uses radialSegments.
 * @returns         A THREE.Group ready to add to the scene.
 */
export function buildSupportMesh(
  nodes:    Map<number, TreeNode>,
  segments: TreeSegment[],
  config:   SupportConfig,
): THREE.Group {
  const group = new THREE.Group();
  group.name  = "tree-support";

  const segs = config.radialSegments;

  for (const seg of segments) {
    const a = nodes.get(seg.startNodeId);
    const b = nodes.get(seg.endNodeId);
    if (!a || !b) continue;

    const len = a.position.distanceTo(b.position);
    if (len < 0.5) continue;

    const r1 = Math.max(seg.radiusStart, 0.05);
    const r2 = Math.max(seg.radiusEnd,   0.05);

    // Cylinder: Three.js CylinderGeometry is oriented along Y axis
    const geo = new THREE.CylinderGeometry(r2, r1, len, segs, 1, false);

    const nodeB = b;
    const mat   = matFor(nodeB.type);
    const mesh  = new THREE.Mesh(geo, mat);

    // Position at midpoint between a and b
    const mid = a.position.clone().lerp(b.position, 0.5);
    mesh.position.copy(mid);

    // Orient from a → b
    const dir = b.position.clone().sub(a.position).normalize();
    const q   = new THREE.Quaternion().setFromUnitVectors(Y_AXIS, dir);
    mesh.quaternion.copy(q);

    group.add(mesh);
  }

  // Small spheres at branch joints make the preview read as a continuous
  // organic tree instead of separate straight sticks.
  for (const node of nodes.values()) {
    if (node.type === "root") continue;
    const r = Math.max(node.radius, 0.1);
    const radiusScale = node.type === "contact" ? 0.75 : 1.05;
    const geo  = new THREE.SphereGeometry(r * radiusScale, segs, Math.ceil(segs * 0.5));
    const mesh = new THREE.Mesh(geo, matFor(node.type));
    mesh.position.copy(node.position);
    group.add(mesh);
  }

  return group;
}

/**
 * Build a lightweight "preview" mesh using lower-resolution geometry.
 * Useful during interactive generation before final quality render.
 */
export function buildPreviewMesh(
  nodes:    Map<number, TreeNode>,
  segments: TreeSegment[],
): THREE.Group {
  const lowConfig = { radialSegments: 5 } as SupportConfig;
  return buildSupportMesh(nodes, segments, lowConfig);
}

/**
 * Build a debug visualisation group — shows node positions as small spheres
 * coloured by type, without branch cylinders.
 */
export function buildDebugGroup(nodes: Map<number, TreeNode>): THREE.Group {
  const group = new THREE.Group();
  group.name  = "tree-support-debug";

  for (const node of nodes.values()) {
    const r   = Math.max(node.radius * 0.4, 0.3);
    const geo  = new THREE.SphereGeometry(r, 6, 4);
    const mesh = new THREE.Mesh(geo, matFor(node.type));
    mesh.position.copy(node.position);
    group.add(mesh);
  }

  return group;
}
