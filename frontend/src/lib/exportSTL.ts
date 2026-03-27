import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

// ── Binary STL format ─────────────────────────────────────────────────────────
//
//  80 bytes  header
//   4 bytes  triangle count (uint32 LE)
//  50 bytes  per triangle:
//    12 bytes  normal   (3 × float32 LE)
//    12 bytes  vertex 0 (3 × float32 LE)
//    12 bytes  vertex 1 (3 × float32 LE)
//    12 bytes  vertex 2 (3 × float32 LE)
//     2 bytes  attribute byte count (uint16, always 0)

const HEADER_BYTES    = 80;
const TRIANGLE_BYTES  = 50;

// ── Triangle collection ───────────────────────────────────────────────────────

type Triangle = {
  normal: THREE.Vector3;
  a:      THREE.Vector3;
  b:      THREE.Vector3;
  c:      THREE.Vector3;
};

function collectTriangles(
  geometry: THREE.BufferGeometry,
  matrix:   THREE.Matrix4,
): Triangle[] {
  const triangles: Triangle[] = [];

  const pos      = geometry.attributes.position;
  const index    = geometry.index;
  const normalMat = new THREE.Matrix3().getNormalMatrix(matrix);

  const a  = new THREE.Vector3();
  const b  = new THREE.Vector3();
  const c  = new THREE.Vector3();
  const ab = new THREE.Vector3();
  const ac = new THREE.Vector3();
  const n  = new THREE.Vector3();

  const faceCount = index ? index.count / 3 : pos.count / 3;

  for (let i = 0; i < faceCount; i++) {
    const i0 = index ? index.getX(i * 3)     : i * 3;
    const i1 = index ? index.getX(i * 3 + 1) : i * 3 + 1;
    const i2 = index ? index.getX(i * 3 + 2) : i * 3 + 2;

    a.fromBufferAttribute(pos, i0).applyMatrix4(matrix);
    b.fromBufferAttribute(pos, i1).applyMatrix4(matrix);
    c.fromBufferAttribute(pos, i2).applyMatrix4(matrix);

    ab.subVectors(b, a);
    ac.subVectors(c, a);
    n.crossVectors(ab, ac).applyMatrix3(normalMat).normalize();

    triangles.push({
      normal: n.clone(),
      a: a.clone(),
      b: b.clone(),
      c: c.clone(),
    });
  }

  return triangles;
}

function collectFromObject(root: THREE.Object3D): Triangle[] {
  const triangles: Triangle[] = [];
  root.updateWorldMatrix(true, true);

  root.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (mesh.isMesh && mesh.geometry) {
      triangles.push(...collectTriangles(mesh.geometry, mesh.matrixWorld));
    }
  });

  return triangles;
}

/**
 * Traverse `root`, bake every mesh's world transform into a cloned geometry,
 * then merge all pieces into one unified BufferGeometry.
 *
 * This ensures the exported model is a single coherent mesh body rather than
 * a collection of disconnected sub-meshes that slicers split into separate parts.
 *
 * Returns null if the object contains no mesh geometry.
 */
function mergeObjectGeometries(root: THREE.Object3D): THREE.BufferGeometry | null {
  root.updateWorldMatrix(true, true);

  const pieces: THREE.BufferGeometry[] = [];

  root.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (!mesh.isMesh || !mesh.geometry) return;

    // Clone and bake the world transform so all pieces share the same space
    const g = mesh.geometry.clone().applyMatrix4(mesh.matrixWorld);

    // Strip every attribute except position — mergeGeometries requires
    // homogeneous attribute sets, and normals will be recomputed below
    for (const key of Object.keys(g.attributes)) {
      if (key !== "position") g.deleteAttribute(key);
    }

    pieces.push(g);
  });

  console.log(`[exportSTL] mergeObjectGeometries: found ${pieces.length} mesh node(s)`);

  if (pieces.length === 0) {
    console.warn("[exportSTL] mergeObjectGeometries: no mesh geometry found — returning null");
    return null;
  }

  const merged = mergeGeometries(pieces, false);
  pieces.forEach((g) => g.dispose());

  if (!merged) {
    console.error("[exportSTL] mergeObjectGeometries: mergeGeometries() returned null — merge failed");
    return null;
  }

  // Recompute per-vertex normals on the unified geometry
  merged.computeVertexNormals();

  const vertexCount   = merged.attributes.position.count;
  const triangleCount = merged.index
    ? merged.index.count / 3
    : vertexCount / 3;
  console.log(`[exportSTL] mergeObjectGeometries: merge succeeded — ${vertexCount} vertices, ${triangleCount} triangles`);

  return merged;
}

// ── Binary STL writer ─────────────────────────────────────────────────────────

function writeBinarySTL(triangles: Triangle[]): ArrayBuffer {
  const buffer = new ArrayBuffer(HEADER_BYTES + 4 + triangles.length * TRIANGLE_BYTES);
  const view   = new DataView(buffer);
  let   offset = 0;

  // Header — 80 bytes ASCII "AutoSlice STL Export" padded with zeros
  const header = "AutoSlice STL Export";
  for (let i = 0; i < HEADER_BYTES; i++) {
    view.setUint8(offset++, i < header.length ? header.charCodeAt(i) : 0);
  }

  // Triangle count
  view.setUint32(offset, triangles.length, true);
  offset += 4;

  // Triangles
  for (const tri of triangles) {
    const writeVec = (v: THREE.Vector3) => {
      view.setFloat32(offset,      v.x, true);
      view.setFloat32(offset + 4,  v.y, true);
      view.setFloat32(offset + 8,  v.z, true);
      offset += 12;
    };

    writeVec(tri.normal);
    writeVec(tri.a);
    writeVec(tri.b);
    writeVec(tri.c);

    // Attribute byte count — always 0
    view.setUint16(offset, 0, true);
    offset += 2;
  }

  return buffer;
}

// ── Download helper ───────────────────────────────────────────────────────────

function triggerDownload(buffer: ArrayBuffer, filename: string): void {
  const blob = new Blob([buffer], { type: "application/octet-stream" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Public API ────────────────────────────────────────────────────────────────

export type ExportOptions = {
  modelFilename?:    string;  // default "model.stl"
  supportsFilename?: string;  // default "supports.stl"
  combined?:         boolean; // export single file with both, default false
  combinedFilename?: string;  // default "model_with_supports.stl"
};

/**
 * Export model and supports as binary STL files.
 *
 * Supports are NEVER merged into the model — they are exported separately
 * (or combined into a single file when `combined: true`).
 *
 * All world transforms are baked before export.
 * Returns the raw ArrayBuffers for both in case the caller needs them
 * (e.g. for upload rather than browser download).
 */
export function exportSTL(
  model:    THREE.Object3D,
  supports: THREE.Object3D | null,
  options:  ExportOptions = {},
): { modelBuffer: ArrayBuffer; supportsBuffer: ArrayBuffer | null } {
  const {
    modelFilename    = "model.stl",
    supportsFilename = "supports.stl",
    combined         = false,
    combinedFilename = "model_with_supports.stl",
  } = options;

  // Merge all model sub-meshes into one unified geometry so slicers receive
  // a single solid body. Fall back to per-mesh traversal if merge fails.
  const mergedModelGeo = mergeObjectGeometries(model);
  let modelTriangles: Triangle[];
  if (mergedModelGeo) {
    console.log("[exportSTL] exportSTL: using merged geometry for model export");
    modelTriangles = collectTriangles(mergedModelGeo, new THREE.Matrix4()); // identity — transform already baked
    mergedModelGeo.dispose();
  } else {
    console.warn("[exportSTL] exportSTL: falling back to collectFromObject for model (merge unavailable)");
    modelTriangles = collectFromObject(model);
  }

  // Supports stay separate by design
  const supportsTriangles = supports ? collectFromObject(supports) : [];

  const modelBuffer    = writeBinarySTL(modelTriangles);
  const supportsBuffer = supportsTriangles.length
    ? writeBinarySTL(supportsTriangles)
    : null;

  if (combined) {
    const allTriangles  = [...modelTriangles, ...supportsTriangles];
    const combinedBuffer = writeBinarySTL(allTriangles);
    triggerDownload(combinedBuffer, combinedFilename);
  } else {
    triggerDownload(modelBuffer, modelFilename);
    if (supportsBuffer) {
      triggerDownload(supportsBuffer, supportsFilename);
    }
  }

  return { modelBuffer, supportsBuffer };
}

/**
 * Export a single Object3D as a binary STL ArrayBuffer without triggering
 * a download.  Useful for server upload or further processing.
 */
export function geometryToSTLBuffer(object: THREE.Object3D): ArrayBuffer {
  const merged = mergeObjectGeometries(object);
  if (merged) {
    const buf = writeBinarySTL(collectTriangles(merged, new THREE.Matrix4()));
    merged.dispose();
    return buf;
  }
  return writeBinarySTL(collectFromObject(object));
}
