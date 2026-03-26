import * as THREE from "three";

// ── Types ──────────────────────────────────────────────────────────────────────

export type LayerPreviewOptions = {
  /** Layer thickness in mm. Default 0.2 */
  layerHeight?: number;
  /** Hard cap on layer count. Default 2000 */
  maxLayers?: number;
};

export type LayerData = {
  /** Zero-based layer index */
  index: number;
  /** Y-height of the sampling plane for this layer */
  y: number;
  /**
   * LineSegments-ready BufferGeometry for the model cross-section.
   * Render as: <lineSegments geometry={layer.modelSegments} />
   * Null when no geometry intersects this layer.
   */
  modelSegments: THREE.BufferGeometry | null;
  /**
   * LineSegments-ready BufferGeometry for the supports cross-section.
   * Null when no supports or no intersection.
   */
  supportsSegments: THREE.BufferGeometry | null;
};

export type LayerPreviewResult = {
  layers:      LayerData[];
  layerCount:  number;
  layerHeight: number;
  /** Lowest sampled Y (clamped to ≥ 0) */
  minY:        number;
  /** Highest sampled Y */
  maxY:        number;
};

// ── Internal triangle buffer ───────────────────────────────────────────────────
//
// World-space triangles stored in flat typed arrays for cache-friendly access.
// minY/maxY per triangle enables fast layer-range rejection.

type TriangleBuffer = {
  ax: Float32Array; ay: Float32Array; az: Float32Array;
  bx: Float32Array; by: Float32Array; bz: Float32Array;
  cx: Float32Array; cy: Float32Array; cz: Float32Array;
  minY: Float32Array;
  maxY: Float32Array;
  count: number;
};

function emptyBuffer(): TriangleBuffer {
  const z = new Float32Array(0);
  return { ax: z, ay: z, az: z, bx: z, by: z, bz: z, cx: z, cy: z, cz: z, minY: z, maxY: z, count: 0 };
}

function collectFromMesh(mesh: THREE.Mesh): TriangleBuffer {
  mesh.updateMatrixWorld(true);
  const geo = mesh.geometry;
  const pos = geo.attributes.position;
  const idx = geo.index;
  const mat = mesh.matrixWorld;
  const count = idx ? idx.count / 3 : pos.count / 3;

  const buf: TriangleBuffer = {
    ax: new Float32Array(count), ay: new Float32Array(count), az: new Float32Array(count),
    bx: new Float32Array(count), by: new Float32Array(count), bz: new Float32Array(count),
    cx: new Float32Array(count), cy: new Float32Array(count), cz: new Float32Array(count),
    minY: new Float32Array(count),
    maxY: new Float32Array(count),
    count,
  };

  const v = new THREE.Vector3();

  for (let i = 0; i < count; i++) {
    const i0 = idx ? idx.getX(i * 3)     : i * 3;
    const i1 = idx ? idx.getX(i * 3 + 1) : i * 3 + 1;
    const i2 = idx ? idx.getX(i * 3 + 2) : i * 3 + 2;

    v.fromBufferAttribute(pos, i0).applyMatrix4(mat);
    buf.ax[i] = v.x; buf.ay[i] = v.y; buf.az[i] = v.z;

    v.fromBufferAttribute(pos, i1).applyMatrix4(mat);
    buf.bx[i] = v.x; buf.by[i] = v.y; buf.bz[i] = v.z;

    v.fromBufferAttribute(pos, i2).applyMatrix4(mat);
    buf.cx[i] = v.x; buf.cy[i] = v.y; buf.cz[i] = v.z;

    buf.minY[i] = Math.min(buf.ay[i], buf.by[i], buf.cy[i]);
    buf.maxY[i] = Math.max(buf.ay[i], buf.by[i], buf.cy[i]);
  }

  return buf;
}

function collectFromGroup(group: THREE.Object3D): TriangleBuffer {
  const parts: TriangleBuffer[] = [];
  group.traverse(child => {
    if ((child as THREE.Mesh).isMesh) parts.push(collectFromMesh(child as THREE.Mesh));
  });
  if (parts.length === 0) return emptyBuffer();

  const total = parts.reduce((s, b) => s + b.count, 0);
  const out: TriangleBuffer = {
    ax: new Float32Array(total), ay: new Float32Array(total), az: new Float32Array(total),
    bx: new Float32Array(total), by: new Float32Array(total), bz: new Float32Array(total),
    cx: new Float32Array(total), cy: new Float32Array(total), cz: new Float32Array(total),
    minY: new Float32Array(total),
    maxY: new Float32Array(total),
    count: total,
  };

  let off = 0;
  for (const b of parts) {
    out.ax.set(b.ax, off); out.ay.set(b.ay, off); out.az.set(b.az, off);
    out.bx.set(b.bx, off); out.by.set(b.by, off); out.bz.set(b.bz, off);
    out.cx.set(b.cx, off); out.cy.set(b.cy, off); out.cz.set(b.cz, off);
    out.minY.set(b.minY, off); out.maxY.set(b.maxY, off);
    off += b.count;
  }
  return out;
}

// ── Slicing ────────────────────────────────────────────────────────────────────
//
// For each triangle that straddles the plane Y=h, find the two edge-plane
// intersection points and emit a line segment.
//
// Edge (P→Q) crosses Y=h when sign(P.y−h) ≠ sign(Q.y−h).
// Intersection: t = (P.y−h)/(P.y−Q.y),  point = P + t*(Q−P)
//
// Uses only plain number arithmetic — zero THREE.Vector3 allocations in the hot path.

function sliceAtY(buf: TriangleBuffer, y: number): THREE.BufferGeometry | null {
  if (buf.count === 0) return null;

  // Over-allocate; trim at end.  Each triangle yields at most 6 floats (2 points × 3 components).
  const out = new Float32Array(buf.count * 6);
  let n = 0;

  for (let i = 0; i < buf.count; i++) {
    if (y < buf.minY[i] || y > buf.maxY[i]) continue; // outside Y range — fast skip

    // Signed distances from plane
    const da = buf.ay[i] - y;
    const db = buf.by[i] - y;
    const dc = buf.cy[i] - y;

    // Collect up to 2 crossing points as (x, z) pairs
    let p0x = 0, p0z = 0, p1x = 0, p1z = 0, found = 0;

    // Edge A→B
    if ((da > 0) !== (db > 0) && (da !== 0 || db !== 0)) {
      const t = da / (da - db);
      if (found === 0) {
        p0x = buf.ax[i] + t * (buf.bx[i] - buf.ax[i]);
        p0z = buf.az[i] + t * (buf.bz[i] - buf.az[i]);
      } else {
        p1x = buf.ax[i] + t * (buf.bx[i] - buf.ax[i]);
        p1z = buf.az[i] + t * (buf.bz[i] - buf.az[i]);
      }
      found++;
    }

    // Edge B→C
    if (found < 2 && (db > 0) !== (dc > 0) && (db !== 0 || dc !== 0)) {
      const t = db / (db - dc);
      if (found === 0) {
        p0x = buf.bx[i] + t * (buf.cx[i] - buf.bx[i]);
        p0z = buf.bz[i] + t * (buf.cz[i] - buf.bz[i]);
      } else {
        p1x = buf.bx[i] + t * (buf.cx[i] - buf.bx[i]);
        p1z = buf.bz[i] + t * (buf.cz[i] - buf.bz[i]);
      }
      found++;
    }

    // Edge C→A
    if (found < 2 && (dc > 0) !== (da > 0) && (dc !== 0 || da !== 0)) {
      const t = dc / (dc - da);
      if (found === 0) {
        p0x = buf.cx[i] + t * (buf.ax[i] - buf.cx[i]);
        p0z = buf.cz[i] + t * (buf.az[i] - buf.cz[i]);
      } else {
        p1x = buf.cx[i] + t * (buf.ax[i] - buf.cx[i]);
        p1z = buf.cz[i] + t * (buf.az[i] - buf.cz[i]);
      }
      found++;
    }

    if (found === 2) {
      out[n++] = p0x; out[n++] = y; out[n++] = p0z;
      out[n++] = p1x; out[n++] = y; out[n++] = p1z;
    }
  }

  if (n === 0) return null;

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(out.subarray(0, n), 3));
  return geo;
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Slice a processed model (and optional supports) into horizontal layers,
 * returning per-layer BufferGeometry objects ready for declarative R3F rendering.
 *
 * Usage in R3F:
 *   const preview = useMemo(() => generateLayerPreview(mesh, supports), [mesh]);
 *   const layer = preview.layers[currentIndex];
 *   return (
 *     <>
 *       {layer.modelSegments && (
 *         <lineSegments geometry={layer.modelSegments}>
 *           <lineBasicMaterial color="#cc2222" />
 *         </lineSegments>
 *       )}
 *       {layer.supportsSegments && (
 *         <lineSegments geometry={layer.supportsSegments}>
 *           <lineBasicMaterial color="#888888" />
 *         </lineSegments>
 *       )}
 *     </>
 *   );
 *
 * For "show all layers up to N", render preview.layers.slice(0, N + 1).
 *
 * NOTE: Call outside the render loop (useMemo / useEffect / worker).
 * For high triangle counts, consider running in a web worker.
 */
export function generateLayerPreview(
  modelMesh: THREE.Mesh,
  supports?:  THREE.Group | null,
  options:    LayerPreviewOptions = {},
): LayerPreviewResult {
  const {
    layerHeight = 0.2,
    maxLayers   = 2000,
  } = options;

  // Collect world-space triangles once (expensive — done before the layer loop)
  const modelBuf    = collectFromMesh(modelMesh);
  const supportsBuf = supports ? collectFromGroup(supports) : null;

  // Derive Y range from model world-space bounding box
  modelMesh.geometry.computeBoundingBox();
  const bbox    = modelMesh.geometry.boundingBox!.clone().applyMatrix4(modelMesh.matrixWorld);
  const minY    = Math.max(0, bbox.min.y);
  const maxY    = bbox.max.y;
  const range   = maxY - minY;

  if (range <= 0) return { layers: [], layerCount: 0, layerHeight, minY, maxY };

  const layerCount = Math.min(maxLayers, Math.ceil(range / layerHeight));
  const layers: LayerData[] = [];

  for (let i = 0; i < layerCount; i++) {
    // Sample at the midpoint of each layer slab
    const y = minY + (i + 0.5) * layerHeight;
    layers.push({
      index:            i,
      y,
      modelSegments:    sliceAtY(modelBuf, y),
      supportsSegments: supportsBuf ? sliceAtY(supportsBuf, y) : null,
    });
  }

  return { layers, layerCount, layerHeight, minY, maxY };
}

/**
 * Dispose all BufferGeometry objects held inside a LayerPreviewResult.
 * Call when the preview is replaced or the component unmounts.
 */
export function disposeLayerPreview(result: LayerPreviewResult): void {
  for (const layer of result.layers) {
    layer.modelSegments?.dispose();
    layer.supportsSegments?.dispose();
  }
}
