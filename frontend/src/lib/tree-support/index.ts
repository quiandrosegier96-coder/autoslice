/**
 * AutoSlice — Tree Support Generator public API.
 *
 * Import the generator:
 *   import { TreeSupportGenerator, generateTreeSupport } from "@/lib/tree-support";
 *
 * Import types:
 *   import type { SupportConfig, TreeSupportResult } from "@/lib/tree-support";
 *
 * Import individual modules:
 *   import { detectOverhangs } from "@/lib/tree-support/overhangDetector";
 */

// ── Main class & convenience function ─────────────────────────────────────────
export { TreeSupportGenerator, generateTreeSupport } from "./TreeSupportGenerator";

// ── Types ─────────────────────────────────────────────────────────────────────
export type {
  NodeType,
  TreeNode,
  TreeSegment,
  OverhangFace,
  OverhangCluster,
  SupportConfig,
  SupportStats,
  TreeSupportResult,
  PrinterConfig,
} from "./types";
export { DEFAULT_CONFIG } from "./types";

// ── Overhang detection ────────────────────────────────────────────────────────
export { detectOverhangs, collectGeometries, computeFloorY } from "./overhangDetector";

// ── Clustering ────────────────────────────────────────────────────────────────
export { clusterOverhangs, groupClustersByXZ } from "./clusterizer";

// ── Graph builder ─────────────────────────────────────────────────────────────
export { buildGraph, estimateVolume } from "./graphBuilder";
export type { GraphResult } from "./graphBuilder";

// ── Collision avoider ─────────────────────────────────────────────────────────
export { avoidCollisions } from "./collisionAvoider";

// ── Mesh builder ──────────────────────────────────────────────────────────────
export { buildSupportMesh, buildPreviewMesh, buildDebugGroup } from "./meshBuilder";
