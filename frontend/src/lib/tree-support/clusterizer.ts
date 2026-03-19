/**
 * AutoSlice — Overhang face clusterizer.
 *
 * Groups nearby overhang faces into "islands" using a 3D spatial grid.
 * Each island becomes one support target (OverhangCluster).
 *
 * Algorithm
 * ─────────
 * 1. Assign each face to a grid cell (floor(pos / cellSize)).
 * 2. Build adjacency: two cells are adjacent if their Manhattan distance ≤ 1.
 * 3. Union-Find merges adjacent non-empty cells into connected components.
 * 4. Each component → one OverhangCluster with centroid, area, bounding box.
 */

import * as THREE from "three";
import type { OverhangFace, OverhangCluster, SupportConfig } from "./types";

// ── Union-Find ────────────────────────────────────────────────────────────────

class UnionFind {
  private parent: number[];
  private rank:   number[];

  constructor(n: number) {
    this.parent = Array.from({ length: n }, (_, i) => i);
    this.rank   = new Array(n).fill(0);
  }

  find(x: number): number {
    if (this.parent[x] !== x) this.parent[x] = this.find(this.parent[x]);
    return this.parent[x];
  }

  union(a: number, b: number): void {
    const ra = this.find(a);
    const rb = this.find(b);
    if (ra === rb) return;
    if (this.rank[ra] < this.rank[rb]) { this.parent[ra] = rb; }
    else if (this.rank[ra] > this.rank[rb]) { this.parent[rb] = ra; }
    else { this.parent[rb] = ra; this.rank[ra]++; }
  }
}

// ── Main clustering function ───────────────────────────────────────────────────

/**
 * Cluster overhang faces into spatially connected islands.
 *
 * @param faces   Overhang faces from detectOverhangs().
 * @param config  Support config — uses clusterCellMm and zDistanceMm.
 * @returns       One OverhangCluster per connected island, sorted by area desc.
 */
export function clusterOverhangs(
  faces:  OverhangFace[],
  config: SupportConfig,
): OverhangCluster[] {
  if (faces.length === 0) return [];

  const cell = config.clusterCellMm;

  // ── 1. Assign grid cells ─────────────────────────────────────────────────
  type CellKey = string;
  const cellToFaces = new Map<CellKey, number[]>();  // key → face indices

  const faceCell = faces.map((f) => {
    const gx = Math.floor(f.centroid.x / cell);
    const gy = Math.floor(f.centroid.y / cell);
    const gz = Math.floor(f.centroid.z / cell);
    const key: CellKey = `${gx},${gy},${gz}`;
    if (!cellToFaces.has(key)) cellToFaces.set(key, []);
    cellToFaces.get(key)!.push(faces.indexOf(f));
    return { gx, gy, gz, key };
  });

  const cellKeys   = Array.from(cellToFaces.keys());
  const keyToIdx   = new Map(cellKeys.map((k, i) => [k, i]));
  const uf         = new UnionFind(cellKeys.length);

  // ── 2. Merge adjacent cells ───────────────────────────────────────────────
  for (let i = 0; i < faces.length; i++) {
    const { gx, gy, gz } = faceCell[i];
    const myIdx = keyToIdx.get(`${gx},${gy},${gz}`)!;

    // Check 26 neighbors (3D Moore neighbourhood)
    for (let dx = -1; dx <= 1; dx++) {
      for (let dy = -1; dy <= 1; dy++) {
        for (let dz = -1; dz <= 1; dz++) {
          if (dx === 0 && dy === 0 && dz === 0) continue;
          const nbKey = `${gx + dx},${gy + dy},${gz + dz}`;
          const nbIdx = keyToIdx.get(nbKey);
          if (nbIdx !== undefined) uf.union(myIdx, nbIdx);
        }
      }
    }
  }

  // ── 3. Group cells by component ───────────────────────────────────────────
  const components = new Map<number, number[]>();  // root → face indices
  for (let i = 0; i < faces.length; i++) {
    const cellIdx = keyToIdx.get(faceCell[i].key)!;
    const root    = uf.find(cellIdx);
    if (!components.has(root)) components.set(root, []);
    components.get(root)!.push(i);
  }

  // ── 4. Build clusters ─────────────────────────────────────────────────────
  let clusterId = 0;
  const clusters: OverhangCluster[] = [];

  for (const faceIndices of components.values()) {
    const clusterFaces = faceIndices.map((i) => faces[i]);

    // Weighted centroid (weight by face area for accuracy)
    const centroid = new THREE.Vector3();
    const box      = new THREE.Box3();
    let totalArea  = 0;

    for (const f of clusterFaces) {
      centroid.addScaledVector(f.centroid, f.area);
      box.expandByPoint(f.centroid);
      totalArea += f.area;
    }
    centroid.divideScalar(totalArea || 1);

    // Average downward normal (used for tip-contact offset direction)
    const avgNormal = new THREE.Vector3();
    for (const f of clusterFaces) avgNormal.add(f.normal);
    avgNormal.normalize();

    // Tip position: centroid shifted slightly in normal direction to stay off surface
    const tipPosition = centroid.clone().addScaledVector(
      avgNormal,
      config.zDistanceMm,
    );

    clusters.push({
      id:          clusterId++,
      centroid,
      area:        totalArea,
      boundingBox: box,
      faces:       clusterFaces,
      tipPosition,
    });
  }

  // Sort by area descending so large overhangs are processed first
  return clusters.sort((a, b) => b.area - a.area);
}

/**
 * Secondary grouping: cluster OverhangClusters themselves by XZ proximity.
 * Used in the graph builder to merge clusters that can share a trunk.
 *
 * @param clusters     Detected overhang clusters.
 * @param radiusMm     XZ merge radius.
 * @returns            Groups of clusters — each group → one trunk.
 */
export function groupClustersByXZ(
  clusters: OverhangCluster[],
  radiusMm: number,
): OverhangCluster[][] {
  if (clusters.length === 0) return [];

  const used   = new Array(clusters.length).fill(false);
  const groups: OverhangCluster[][] = [];

  for (let i = 0; i < clusters.length; i++) {
    if (used[i]) continue;
    const group = [clusters[i]];
    used[i] = true;

    for (let j = i + 1; j < clusters.length; j++) {
      if (used[j]) continue;
      const dx = clusters[i].centroid.x - clusters[j].centroid.x;
      const dz = clusters[i].centroid.z - clusters[j].centroid.z;
      if (Math.sqrt(dx * dx + dz * dz) <= radiusMm) {
        group.push(clusters[j]);
        used[j] = true;
      }
    }

    groups.push(group);
  }

  return groups;
}
