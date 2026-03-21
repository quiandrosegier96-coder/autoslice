/**
 * AutoSlice — TreeSupportGenerator
 *
 * Main orchestrator class that wires together:
 *   1. Overhang detection
 *   2. Spatial clustering
 *   3. Tree graph construction
 *   4. Collision avoidance (optional)
 *   5. Mesh generation
 *
 * Usage
 * ─────
 *   const gen = new TreeSupportGenerator(config);
 *   const result = gen.generate(sceneObject);
 *   scene.add(result.supportMesh);
 */

import * as THREE from "three";
import type { SupportConfig, TreeSupportResult, SupportStats } from "./types";
import { DEFAULT_CONFIG } from "./types";
import { detectOverhangs, collectGeometries, computeFloorY, filterSupportedFaces } from "./overhangDetector";
import { clusterOverhangs, groupClustersByXZ } from "./clusterizer";
import { buildGraph, estimateVolume } from "./graphBuilder";
import { avoidCollisions } from "./collisionAvoider";
import { buildSupportMesh, buildDebugGroup } from "./meshBuilder";

export class TreeSupportGenerator {
  private config: SupportConfig;

  constructor(config: Partial<SupportConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /** Update configuration. */
  setConfig(config: Partial<SupportConfig>): void {
    this.config = { ...this.config, ...config };
  }

  /**
   * Generate tree supports for a scene object.
   *
   * @param sceneObject  The model to support (THREE.Object3D — can be a Group).
   * @param showDebug    If true, populate result.debugFaces for overlay rendering.
   * @returns            Full TreeSupportResult.
   */
  generate(
    sceneObject: THREE.Object3D,
    showDebug = false,
  ): TreeSupportResult {
    const config = this.config;

    // ── 1. Overhang detection ──────────────────────────────────────────────
    const plateY  = computeFloorY(sceneObject);
    const geoList = collectGeometries(sceneObject);

    const allFaces = geoList.flatMap(({ geometry, matrixWorld }) =>
      detectOverhangs(geometry, matrixWorld, config.overhangAngleDeg, plateY),
    );

    // ── 1b. Collect all model meshes (needed for raycast filter + collision) ─
    const allMeshes: THREE.Mesh[] = [];
    sceneObject.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) allMeshes.push(child as THREE.Mesh);
    });

    // ── 1c. Downward raycast filter — drop self-supported faces ─────────────
    // Any face that has model geometry directly below it does not need support.
    const supportedFaces = filterSupportedFaces(allFaces, allMeshes, plateY);

    // ── 2. Clustering ──────────────────────────────────────────────────────
    const clusters = clusterOverhangs(supportedFaces, config);

    // Primary grouping: clusters that share a trunk
    const primaryGroups = groupClustersByXZ(clusters, config.mergeDistanceMm);

    // ── 3. Graph construction ──────────────────────────────────────────────
    const graphResult = buildGraph(primaryGroups, plateY, config);

    // ── 4. Collision avoidance against all model meshes ───────────────────
    avoidCollisions(graphResult, sceneObject, config);

    // ── 5. Mesh generation ─────────────────────────────────────────────────
    const supportMesh = buildSupportMesh(graphResult.nodes, graphResult.segments, config);

    // ── 6. Stats ───────────────────────────────────────────────────────────
    let trunkCount   = 0;
    let tipCount     = 0;
    let contactCount = 0;
    for (const node of graphResult.nodes.values()) {
      if (node.type === "trunk" || node.type === "root") trunkCount++;
      if (node.type === "tip")     tipCount++;
      if (node.type === "contact") contactCount++;
    }

    const stats: SupportStats = {
      trunkCount,
      tipCount,
      contactCount,
      clusterCount:       clusters.length,
      segmentCount:       graphResult.segments.length,
      nodeCount:          graphResult.nodes.size,
      estimatedVolumeMm3: estimateVolume(graphResult.segments, graphResult.nodes),
    };

    const result: TreeSupportResult = {
      supportType: "tree",
      clusters,
      nodes:       graphResult.nodes,
      segments:    graphResult.segments,
      supportMesh,
      stats,
    };

    if (showDebug) {
      result.debugGroup = buildDebugGroup(graphResult.nodes);
      result.debugFaces = { allOverhangs: allFaces, needsSupport: supportedFaces };
    }

    return result;
  }

  /**
   * Quick check: does the object have any overhangs at all?
   * Much cheaper than full generation — useful for UI gating.
   */
  hasOverhangs(sceneObject: THREE.Object3D): boolean {
    const plateY  = computeFloorY(sceneObject);
    const geoList = collectGeometries(sceneObject);

    for (const { geometry, matrixWorld } of geoList) {
      const faces = detectOverhangs(
        geometry, matrixWorld, this.config.overhangAngleDeg, plateY,
      );
      if (faces.length > 0) return true;
    }
    return false;
  }

  /** Return current config. */
  getConfig(): Readonly<SupportConfig> {
    return { ...this.config };
  }
}

/** Convenience one-shot function. */
export function generateTreeSupport(
  sceneObject: THREE.Object3D,
  config:      Partial<SupportConfig> = {},
  showDebug = false,
): TreeSupportResult {
  return new TreeSupportGenerator(config).generate(sceneObject, showDebug);
}
