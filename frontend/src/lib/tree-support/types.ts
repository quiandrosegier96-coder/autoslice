/**
 * AutoSlice — Tree Support Generator types.
 *
 * All coordinates are in Three.js world space (Y-up, mm).
 * The build plate is at Y = 0 (after model centering).
 */

import * as THREE from "three";

// ── Node types ────────────────────────────────────────────────────────────────

export type NodeType = "root" | "trunk" | "branch" | "tip" | "contact" | "waypoint";

export interface TreeNode {
  id:       number;
  position: THREE.Vector3;
  radius:   number;
  parentId: number | null;
  childIds: number[];
  type:     NodeType;
}

// ── Segment ───────────────────────────────────────────────────────────────────

export interface TreeSegment {
  id:          number;
  startNodeId: number;
  endNodeId:   number;
  radiusStart: number;
  radiusEnd:   number;
}

// ── Overhang detection ────────────────────────────────────────────────────────

export interface OverhangFace {
  /** Triangle index in the source BufferGeometry. */
  index:      number;
  normal:     THREE.Vector3;
  centroid:   THREE.Vector3;
  vertices:   [THREE.Vector3, THREE.Vector3, THREE.Vector3];
  area:       number;
  /** dot(normal, gravity): 0 = horizontal, 1 = fully downward. */
  overhangDot: number;
}

// ── Cluster ───────────────────────────────────────────────────────────────────

export interface OverhangCluster {
  id:          number;
  centroid:    THREE.Vector3;
  area:        number;
  boundingBox: THREE.Box3;
  faces:       OverhangFace[];
  /** Where the support tip contacts the model — centroid minus zDistance. */
  tipPosition: THREE.Vector3;
}

// ── Config ────────────────────────────────────────────────────────────────────

export interface SupportConfig {
  // Detection
  overhangAngleDeg:    number;   // default 45 — faces more than this below horizontal
  // Branch geometry (mm)
  branchAngleDeg:      number;   // default 40 — max angle from vertical
  trunkRadiusMm:       number;   // default 2.0
  branchRadiusMm:      number;   // default 1.0
  tipRadiusMm:         number;   // default 0.5
  collisionMarginMm:   number;   // default 0.8 — clearance from mesh
  mergeDistanceMm:     number;   // default 25 — XZ distance at which clusters share a trunk
  zDistanceMm:         number;   // default 0.2 — gap between tip and overhang surface
  xyDistanceMm:        number;   // default 0.4 — lateral clearance
  buildPlateOnly:      boolean;  // roots only on Y=0 plate
  // Printer
  nozzleDiameterMm:    number;   // default 0.4
  layerHeightMm:       number;   // default 0.2
  // Clustering
  clusterCellMm:       number;   // default 5 — spatial grid cell size
  // Rendering
  radialSegments:      number;   // default 8 — cylinder resolution
}

export interface PrinterConfig {
  buildVolume: { x: number; y: number; z: number };
  nozzleDiameter: number;
  layerHeight: number;
}

// ── Output ────────────────────────────────────────────────────────────────────

export interface SupportStats {
  trunkCount:          number;
  tipCount:            number;
  estimatedVolumeMm3:  number;
  contactCount:        number;
  clusterCount:        number;
  segmentCount:        number;
  nodeCount:           number;
}

/** Minimal graph interface shared between generator and collision avoider. */
export interface GraphResult {
  nodes:    Map<number, TreeNode>;
  segments: TreeSegment[];
}

export interface TreeSupportResult {
  supportType:  "tree";
  clusters:     OverhangCluster[];
  nodes:        Map<number, TreeNode>;
  segments:     TreeSegment[];
  supportMesh:  THREE.Group;
  debugGroup?:  THREE.Group;
  stats:        SupportStats;
  /** Populated only when showDebug = true. Used by DebugFaceOverlay. */
  debugFaces?: {
    /** All downward-facing faces (shown red). */
    allOverhangs: OverhangFace[];
    /** Faces that pass the downward raycast filter (shown orange). */
    needsSupport: OverhangFace[];
  };
}

// ── Defaults ──────────────────────────────────────────────────────────────────

export const DEFAULT_CONFIG: SupportConfig = {
  overhangAngleDeg:  45,
  branchAngleDeg:    42,
  trunkRadiusMm:     1.25,
  branchRadiusMm:    0.62,
  tipRadiusMm:       0.3,
  collisionMarginMm: 0.8,
  mergeDistanceMm:   10.0,
  zDistanceMm:       0.2,
  xyDistanceMm:      0.4,
  buildPlateOnly:    true,
  nozzleDiameterMm:  0.4,
  layerHeightMm:     0.2,
  clusterCellMm:     3.5,
  radialSegments:    12,
};
