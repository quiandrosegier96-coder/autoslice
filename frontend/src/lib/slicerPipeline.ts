import * as THREE from "three";
import { flattenModelToSingleGeometry } from "./flattenModel";
import { autoOrientGeometry }           from "./autoOrient";
import { normalizeModelOnBed }          from "./normalizeModel";
import { detectOverhangFaces }          from "./detectOverhangFaces";
import { generateSupports }             from "./generateSupports";
import { exportSTL }                    from "./exportSTL";
import type { SupportOptions }          from "./generateSupports";
import type { ExportOptions }           from "./exportSTL";

// ── Types ──────────────────────────────────────────────────────────────────────

export type PipelineOptions = {
  /** Overhang angle threshold in degrees. Default 50. */
  overhangAngleDeg?: number;
  /** Auto-orient before placing on bed. Default true. */
  autoOrient?: boolean;
  /** Support generation options. */
  supports?: SupportOptions;
  /** STL export options. */
  export?: ExportOptions;
};

export type PipelineResult = {
  /** Final model mesh — repaired, oriented, placed on bed. */
  modelMesh: THREE.Mesh;
  /** Support pillars as a separate group. Null if no overhangs found. */
  supportsGroup: THREE.Group | null;
  /** Number of support pillars generated. */
  pillarCount: number;
  /** Number of overhang faces detected. */
  overhangCount: number;
  /** Raw STL buffers — use for upload or further processing. */
  buffers: {
    model:    ArrayBuffer;
    supports: ArrayBuffer | null;
  };
};

// ── Default material ───────────────────────────────────────────────────────────

function modelMaterial(): THREE.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({
    color:     0xcc2222,
    roughness: 0.6,
    metalness: 0.1,
  });
}

// ── Pipeline ───────────────────────────────────────────────────────────────────

/**
 * Full slicer pipeline.
 *
 * Steps:
 *  1. Flatten all meshes in the scene into a single repaired BufferGeometry
 *  2. Auto-orient for minimum height + minimum overhang (optional)
 *  3. Place on bed (center X/Z, bottom at Y = 0)
 *  4. Detect overhang faces
 *  5. Generate support pillars via downward raycast
 *  6. Export model + supports as binary STL
 *
 * @param uploadedScene  Raw THREE.Object3D from the loader (e.g. ThreeMFLoader)
 * @param options        Pipeline configuration
 * @returns              PipelineResult with meshes, stats and STL buffers
 */
export function runSlicerPipeline(
  uploadedScene: THREE.Object3D,
  options:       PipelineOptions = {},
): PipelineResult {
  const {
    overhangAngleDeg = 50,
    autoOrient       = true,
    supports:   supportOpts = {},
    export:     exportOpts  = {},
  } = options;

  // ── Step 1: Flatten + repair ───────────────────────────────────────────────
  let geometry = flattenModelToSingleGeometry(uploadedScene);

  // ── Step 2: Auto-orient ────────────────────────────────────────────────────
  if (autoOrient) {
    geometry = autoOrientGeometry(geometry);
  }

  // ── Step 3: Place on bed ───────────────────────────────────────────────────
  const modelMesh = new THREE.Mesh(geometry, modelMaterial());
  normalizeModelOnBed(modelMesh);

  // ── Step 4: Overhang detection ─────────────────────────────────────────────
  const overhangFaces = detectOverhangFaces(modelMesh.geometry, overhangAngleDeg);

  // ── Step 5: Support generation ─────────────────────────────────────────────
  let supportsGroup: THREE.Group | null = null;
  let pillarCount = 0;

  if (overhangFaces.length > 0) {
    const result  = generateSupports(overhangFaces, modelMesh, supportOpts);
    supportsGroup = result.group;
    pillarCount   = result.pillarCount;
  }

  // ── Step 6: STL export ─────────────────────────────────────────────────────
  const { modelBuffer, supportsBuffer } = exportSTL(
    modelMesh,
    supportsGroup,
    exportOpts,
  );

  return {
    modelMesh,
    supportsGroup,
    pillarCount,
    overhangCount: overhangFaces.length,
    buffers: {
      model:    modelBuffer,
      supports: supportsBuffer,
    },
  };
}
