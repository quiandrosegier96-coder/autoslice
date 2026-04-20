/**
 * AutoSlice — Tree support graph builder.
 *
 * Converts overhang clusters into a directed tree graph:
 *   root (build plate)  →  trunk node  →  [sub-trunk]  →  tip (overhang contact)
 *
 * Algorithm (all in Three.js Y-up world space)
 * ─────────────────────────────────────────────
 * 1. Primary group:  cluster clusters by XZ proximity (mergeDistanceMm).
 *    Each group → one trunk.
 *
 * 2. For each group:
 *    a. Root node at (cx, plateY, cz) — build plate.
 *    b. Trunk top node at branchY = plateY + (lowestCluster.y - plateY) * BRANCH_FRAC.
 *       Constrained so that the angle root→trunk ≤ branchAngleDeg from vertical.
 *    c. Groups with ≤ 3 clusters → direct branches from trunk top → tip.
 *    d. Groups with > 3 clusters → secondary sub-clustering → sub-trunks → tips.
 *
 * 3. Branch splay: tips too close to trunk centroid are pushed out so
 *    no branch appears as a vertical pillar.
 *
 * 4. Radius assignment: geometric taper per level (trunk → branch → tip).
 */

import * as THREE from "three";
import type { TreeNode, TreeSegment, OverhangCluster, SupportConfig, NodeType } from "./types";

// ── Constants ─────────────────────────────────────────────────────────────────
const BRANCH_FRAC      = 0.55;   // trunk top at this fraction of [plateY..tipY]
const SPLAY_MULT       = 1.20;   // outward lean multiplier for tip branches
const MIN_XZ_SPREAD    = 3.0;    // minimum XZ displacement from parent (mm)
const TAPER            = 0.74;   // radius multiplier per level
const TRUNK_R_MIN      = 1.5;
const TRUNK_R_MAX      = 4.0;
const BRANCH_R_MIN     = 0.6;
const MIN_SEGMENT_MM   = 1.5;

// ── Node counter ──────────────────────────────────────────────────────────────
let _nextId = 0;
function resetIds() { _nextId = 0; }
function newId() { return _nextId++; }

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeNode(
  position: THREE.Vector3,
  radius:   number,
  parentId: number | null,
  type:     NodeType,
): TreeNode {
  const node: TreeNode = {
    id:       newId(),
    position: position.clone(),
    radius,
    parentId,
    childIds: [],
    type,
  };
  return node;
}

/** Compute XZ centroid of a group of clusters. */
function xzCentroid(clusters: OverhangCluster[]): THREE.Vector3 {
  const c = new THREE.Vector3();
  for (const cl of clusters) c.add(cl.centroid);
  c.divideScalar(clusters.length);
  c.y = 0;  // XZ plane only
  return c;
}

/** Lowest Y among all centroids in a group. */
function minY(clusters: OverhangCluster[]): number {
  return Math.min(...clusters.map((c) => c.tipPosition.y));
}

/**
 * Clamp the branch node Y so the angle from root to branch ≤ maxAngleDeg.
 * Also ensures: plateY + 2mm ≤ branchY ≤ lowestTipY - 0.5mm.
 */
function constrainBranchY(
  cx: number, cz: number,
  plateY: number,
  clusters: OverhangCluster[],
  tanMax: number,
): number {
  const lowestTipY = minY(clusters);
  let branchY = plateY + (lowestTipY - plateY) * BRANCH_FRAC;

  for (const cl of clusters) {
    const dx = cx - cl.tipPosition.x;
    const dz = cz - cl.tipPosition.z;
    const dXZ = Math.sqrt(dx * dx + dz * dz);
    if (dXZ > 1e-6 && tanMax > 1e-6) {
      // tipY - branchY >= dXZ / tanMax
      const maxBranchY = cl.tipPosition.y - dXZ / tanMax;
      branchY = Math.min(branchY, maxBranchY);
    }
  }

  branchY = Math.max(branchY, plateY + 2.0);
  branchY = Math.min(branchY, Math.max(lowestTipY - 0.5, plateY + 0.5));
  return branchY;
}

/** Apply splay to a tip position so it has a visible lean from parent. */
function splayedTip(parent: THREE.Vector3, tip: THREE.Vector3): THREE.Vector3 {
  const dx = tip.x - parent.x;
  const dz = tip.z - parent.z;
  const d  = Math.sqrt(dx * dx + dz * dz);

  let ndx = dx;
  let ndz = dz;

  if (d < MIN_XZ_SPREAD) {
    if (d < 1e-6) { ndx = MIN_XZ_SPREAD; ndz = 0; }
    else { const s = MIN_XZ_SPREAD / d; ndx *= s; ndz *= s; }
  } else {
    ndx *= SPLAY_MULT;
    ndz *= SPLAY_MULT;
  }

  return new THREE.Vector3(parent.x + ndx, tip.y, parent.z + ndz);
}

/**
 * Secondary grouping: cluster clusters in a trunk group by XZ proximity.
 * Used to build sub-trunks for large groups.
 */
function subGroupClusters(
  clusters: OverhangCluster[],
  radius:   number,
): OverhangCluster[][] {
  const used: boolean[] = new Array(clusters.length).fill(false);
  const groups: OverhangCluster[][] = [];
  for (let i = 0; i < clusters.length; i++) {
    if (used[i]) continue;
    const grp = [clusters[i]];
    used[i] = true;
    for (let j = i + 1; j < clusters.length; j++) {
      if (used[j]) continue;
      const dx = clusters[i].centroid.x - clusters[j].centroid.x;
      const dz = clusters[i].centroid.z - clusters[j].centroid.z;
      if (Math.sqrt(dx * dx + dz * dz) <= radius) {
        grp.push(clusters[j]);
        used[j] = true;
      }
    }
    groups.push(grp);
  }
  return groups;
}

// ── Main builder ──────────────────────────────────────────────────────────────

export interface GraphResult {
  nodes:    Map<number, TreeNode>;
  segments: TreeSegment[];
}

/**
 * Build a tree support graph from clustered overhang targets.
 *
 * @param primaryGroups  Pre-grouped clusters (one group → one trunk).
 * @param plateY         Build-plate Y coordinate.
 * @param config         Support configuration.
 */
export function buildGraph(
  primaryGroups: OverhangCluster[][],
  plateY:        number,
  config:        SupportConfig,
): GraphResult {
  resetIds();

  const nodes    = new Map<number, TreeNode>();
  const segments: TreeSegment[] = [];
  let   segId    = 0;

  const tanMax  = Math.tan(THREE.MathUtils.degToRad(config.branchAngleDeg));

  function addNode(n: TreeNode): TreeNode {
    nodes.set(n.id, n);
    if (n.parentId !== null) {
      const parent = nodes.get(n.parentId);
      if (parent) parent.childIds.push(n.id);
    }
    return n;
  }

  function addSegment(a: TreeNode, b: TreeNode): void {
    const len = a.position.distanceTo(b.position);
    if (len < MIN_SEGMENT_MM) return;
    segments.push({
      id:          segId++,
      startNodeId: a.id,
      endNodeId:   b.id,
      radiusStart: a.radius,
      radiusEnd:   b.radius,
    });
  }

  // ── Process each primary group (one trunk per group) ──────────────────────
  for (const group of primaryGroups) {
    const n = group.length;

    // Trunk radius scales with number of supported clusters
    const trunkRBase = Math.min(TRUNK_R_MIN + Math.sqrt(n) * 0.5, TRUNK_R_MAX);
    const trunkRTop  = trunkRBase * TAPER;

    // Trunk XZ centroid
    const centXZ = xzCentroid(group);
    const cx = centXZ.x;
    const cz = centXZ.z;

    // Branch node Y
    const branchY = constrainBranchY(cx, cz, plateY, group, tanMax);

    // Root node (build plate)
    const root = addNode(makeNode(new THREE.Vector3(cx, plateY, cz), trunkRBase, null, "root"));

    // Trunk top node (branching point)
    const trunkTop = addNode(makeNode(new THREE.Vector3(cx, branchY, cz), trunkRTop, root.id, "trunk"));
    addSegment(root, trunkTop);

    if (n <= 3) {
      // ── Direct branches: trunk top → each tip ──────────────────────────
      for (const cl of group) {
        const splayed = splayedTip(trunkTop.position, cl.tipPosition);
        const tip = addNode(makeNode(splayed, config.tipRadiusMm, trunkTop.id, "tip"));
        addSegment(trunkTop, tip);

        // Contact node: placed at the overhang tip position.
        // The tip node is splayed outward, so the tip→contact segment
        // approaches the mesh from the side — collision avoider handles it.
        const contact = addNode(makeNode(
          cl.tipPosition.clone(),
          config.tipRadiusMm * 0.6,
          tip.id,
          "contact",
        ));
        addSegment(tip, contact);
      }
    } else {
      // ── Two-level: sub-trunk → tips ────────────────────────────────────
      const subGroups = subGroupClusters(group, config.mergeDistanceMm * 0.5);
      const subBranchR = trunkRTop * TAPER;

      for (const sub of subGroups) {
        const subCentXZ = xzCentroid(sub);
        const subMinY   = minY(sub);

        // Sub-trunk top: halfway between trunk top and lowest sub-cluster
        const rawSubY   = branchY + (subMinY - branchY) * 0.55;
        const subY      = Math.max(Math.min(rawSubY, subMinY - 0.5), branchY + 0.5);

        // Splay sub-trunk endpoint from trunk centroid
        const splSubPos = splayedTip(
          trunkTop.position,
          new THREE.Vector3(subCentXZ.x, subY, subCentXZ.z),
        );
        splSubPos.y = subY;

        const subTrunk = addNode(makeNode(splSubPos, subBranchR, trunkTop.id, "branch"));
        addSegment(trunkTop, subTrunk);

        const tipR = Math.max(subBranchR * TAPER, BRANCH_R_MIN);

        for (const cl of sub) {
          const splayed = splayedTip(subTrunk.position, cl.tipPosition);
          const tip = addNode(makeNode(splayed, config.tipRadiusMm, subTrunk.id, "tip"));
          addSegment(subTrunk, tip);

          const contact = addNode(makeNode(
            cl.tipPosition.clone(),
            config.tipRadiusMm * 0.6,
            tip.id,
            "contact",
          ));
          addSegment(tip, contact);

          void tipR; // radius already assigned via config.tipRadiusMm
        }
      }
    }
  }

  return { nodes, segments };
}

/**
 * Estimate support volume in mm³ (sum of truncated-cone volumes per segment).
 */
export function estimateVolume(
  segments: TreeSegment[],
  nodes:    Map<number, TreeNode>,
): number {
  let vol = 0;
  for (const seg of segments) {
    const a = nodes.get(seg.startNodeId);
    const b = nodes.get(seg.endNodeId);
    if (!a || !b) continue;
    const h  = a.position.distanceTo(b.position);
    const r1 = seg.radiusStart;
    const r2 = seg.radiusEnd;
    // Truncated cone: V = π/3 * h * (r1² + r1*r2 + r2²)
    vol += (Math.PI / 3) * h * (r1 * r1 + r1 * r2 + r2 * r2);
  }
  return vol;
}
