import * as THREE from "three";
import type { OverhangFace } from "./detectOverhangFaces";

// ── Validation helpers ─────────────────────────────────────────────────────────

function isValidVec3(v: THREE.Vector3): boolean {
  return !isNaN(v.x) && !isNaN(v.y) && !isNaN(v.z) &&
         isFinite(v.x) && isFinite(v.y) && isFinite(v.z);
}

// ── Types ──────────────────────────────────────────────────────────────────────

export type TreeSupportOptions = {
  trunkRadius?:       number;   // mm, default 1.2
  branchRadius?:      number;   // mm, default 0.7
  tipRadius?:         number;   // mm, default 0.3
  maxBranchAngleDeg?: number;   // default 45
  clusterDistance?:   number;   // mm, default 8
  radialSegments?:    number;   // cylinder resolution, default 8
  material?:          THREE.Material;
  debug?:             boolean;  // attach debug group as child named "__debug__"
  baseFlare?:         boolean;  // add flared skirt at bed for adhesion, default true
  baseFlareRadius?:   number;   // multiplier on trunkRadius, default 2.2
  baseFlareHeight?:   number;   // mm, default 1.5
  // ── Printability validation ────────────────────────────────────────────────
  /** Minimum diameter (mm) of any branch or tip member. Default 0.8. */
  minimumBranchThickness?:   number;
  /** Maximum branch length (mm) before the branch is skipped as unprintable. Default 40. */
  maximumUnsupportedLength?: number;
  /** XZ radius (mm) one tip is assumed to "cover". Tips within this radius of a
   *  higher-priority tip are suppressed before clustering. Default = clusterDistance/2. */
  supportCoverageRadius?:    number;
};

type Cluster = {
  centroid: THREE.Vector3;
  points:   THREE.Vector3[];
};

// ── Default material ───────────────────────────────────────────────────────────

function defaultMaterial(): THREE.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({
    color:       0x888888,
    transparent: true,
    opacity:     0.65,
    depthWrite:  false,
  });
}

// ── Clustering ─────────────────────────────────────────────────────────────────
//
// Greedy spatial clustering: assign each point to the nearest existing cluster
// centroid within clusterDistance; otherwise start a new cluster.
// Centroid is recomputed incrementally.

function clusterPoints(
  points:          THREE.Vector3[],
  clusterDistance: number,
): Cluster[] {
  const clusters: Cluster[] = [];

  for (const pt of points) {
    let nearest: Cluster | null = null;
    let nearestDist = Infinity;

    for (const cl of clusters) {
      // Compare XZ distance only — points at different Y heights can share a trunk
      const dx = cl.centroid.x - pt.x;
      const dz = cl.centroid.z - pt.z;
      const d  = Math.sqrt(dx * dx + dz * dz);
      if (d < nearestDist) { nearestDist = d; nearest = cl; }
    }

    if (nearest && nearestDist < clusterDistance) {
      nearest.points.push(pt);
      // Recompute centroid as mean of all cluster points
      nearest.centroid.set(0, 0, 0);
      for (const p of nearest.points) nearest.centroid.add(p);
      nearest.centroid.divideScalar(nearest.points.length);
    } else {
      clusters.push({ centroid: pt.clone(), points: [pt] });
    }
  }

  return clusters;
}

// ── Cluster merging ────────────────────────────────────────────────────────────
//
// After the initial greedy pass, iteratively merge any two clusters whose XZ
// centroids are within mergeDistance.  Keeps trunk count low in dense areas.

function mergeClusters(clusters: Cluster[], mergeDistance: number): Cluster[] {
  const out = clusters.slice();
  let changed = true;
  while (changed) {
    changed = false;
    outer: for (let i = 0; i < out.length; i++) {
      for (let j = i + 1; j < out.length; j++) {
        const dx = out[i].centroid.x - out[j].centroid.x;
        const dz = out[i].centroid.z - out[j].centroid.z;
        if (Math.sqrt(dx * dx + dz * dz) < mergeDistance) {
          out[i].points.push(...out[j].points);
          out[i].centroid.set(0, 0, 0);
          for (const p of out[i].points) out[i].centroid.add(p);
          out[i].centroid.divideScalar(out[i].points.length);
          out.splice(j, 1);
          changed = true;
          break outer;
        }
      }
    }
  }
  return out;
}

// ── Geometry builders ──────────────────────────────────────────────────────────

function makeCylinder(
  topPos:    THREE.Vector3,
  bottomPos: THREE.Vector3,
  topR:      number,
  bottomR:   number,
  segments:  number,
  material:  THREE.Material,
): THREE.Mesh | null {
  if (!isValidVec3(topPos) || !isValidVec3(bottomPos)) return null;
  const dir    = new THREE.Vector3().subVectors(topPos, bottomPos);
  const height = dir.length();
  if (height < 0.01) return null; // zero-length — skip

  const geo  = new THREE.CylinderGeometry(topR, bottomR, height, segments, 1);
  const mesh = new THREE.Mesh(geo, material);

  // Default cylinder axis is +Y; rotate to align with dir
  const axis   = new THREE.Vector3(0, 1, 0);
  const dirN   = dir.clone().normalize();
  const quat   = new THREE.Quaternion().setFromUnitVectors(axis, dirN);
  mesh.quaternion.copy(quat);
  mesh.position.copy(bottomPos).addScaledVector(dirN, height / 2);

  return mesh;
}

function makeSphere(pos: THREE.Vector3, radius: number, material: THREE.Material): THREE.Mesh | null {
  if (!isValidVec3(pos)) return null;
  const geo  = new THREE.SphereGeometry(radius, 6, 6);
  const mesh = new THREE.Mesh(geo, material);
  mesh.position.copy(pos);
  return mesh;
}

// ── Branch angle clamping ──────────────────────────────────────────────────────
//
// Given a tip point and a trunk base on the XZ plane, return the actual branch
// attachment point on the trunk respecting maxBranchAngle.
// If the overhang point is directly above the trunk base, no angle clamping needed.

function clampBranchBase(
  tipPos:          THREE.Vector3,
  trunkBaseXZ:     THREE.Vector3, // y = 0
  maxBranchAngleDeg: number,
): THREE.Vector3 {
  // Horizontal offset from trunk axis to tip
  const dx = tipPos.x - trunkBaseXZ.x;
  const dz = tipPos.z - trunkBaseXZ.z;
  const horizDist = Math.sqrt(dx * dx + dz * dz);
  const tipY      = tipPos.y;

  if (tipY <= 0 || horizDist < 0.001) {
    return new THREE.Vector3(trunkBaseXZ.x, 0, trunkBaseXZ.z);
  }

  // Maximum horizontal offset at this height given the angle constraint
  const maxHoriz = tipY * Math.tan(THREE.MathUtils.degToRad(maxBranchAngleDeg));

  // Trunk climbs straight up; branch attaches at the height where it can just
  // reach the tip at the allowed angle
  let attachY: number;
  if (horizDist <= maxHoriz) {
    // Tip is within angle — branch attaches at Y=0 (bed level)
    attachY = 0;
  } else {
    // Tip is too far out; attach higher up the trunk so angle is respected
    // tan(angle) = horizDist / (tipY - attachY)
    // attachY = tipY - horizDist / tan(angle)
    attachY = tipY - horizDist / Math.tan(THREE.MathUtils.degToRad(maxBranchAngleDeg));
    attachY = Math.max(0, attachY);
  }

  return new THREE.Vector3(trunkBaseXZ.x, attachY, trunkBaseXZ.z);
}

// ── Collision helpers ──────────────────────────────────────────────────────────

const _raycaster = new THREE.Raycaster(); // reused — avoid per-call allocation

/**
 * Cast a ray from `from` toward `to` against modelMesh.
 * Returns the distance to the first non-self hit, or null if path is clear.
 */
function raycastBranchPath(
  from:       THREE.Vector3,
  to:         THREE.Vector3,
  modelMesh:  THREE.Mesh,
  selfEps = 0.1,
): number | null {
  const dir = new THREE.Vector3().subVectors(to, from);
  const len = dir.length();
  if (len < 0.001) return null;
  _raycaster.set(from, dir.divideScalar(len));
  _raycaster.near = selfEps;
  _raycaster.far  = len;
  const hits = _raycaster.intersectObject(modelMesh, false);
  return hits.length > 0 ? hits[0].distance : null;
}

/**
 * Jordan-curve inside-mesh test: odd +Y hit count ≈ inside.
 */
function isInsideMesh(pt: THREE.Vector3, modelMesh: THREE.Mesh): boolean {
  _raycaster.set(pt, new THREE.Vector3(0, 1, 0));
  _raycaster.near = 0.001;
  _raycaster.far  = Infinity;
  return (_raycaster.intersectObject(modelMesh, false).length % 2) === 1;
}

// ── Tip deduplication ─────────────────────────────────────────────────────────
//
// Removes tips within `minSpacing` of an already-kept tip.

function deduplicateTips(
  tips:       THREE.Vector3[],
  minSpacing: number,
): THREE.Vector3[] {
  const kept: THREE.Vector3[] = [];
  outer: for (const tip of tips) {
    for (const k of kept) {
      if (k.distanceTo(tip) < minSpacing) continue outer;
    }
    kept.push(tip);
  }
  return kept;
}

// ── Debug geometry helpers ────────────────────────────────────────────────────

const _DBG_MATS: Record<number, THREE.MeshBasicMaterial> = {};
function dbgMat(hex: number): THREE.MeshBasicMaterial {
  if (!_DBG_MATS[hex]) {
    _DBG_MATS[hex] = new THREE.MeshBasicMaterial({ color: hex, depthWrite: false, transparent: true, opacity: 0.85 });
  }
  return _DBG_MATS[hex];
}

function dbgSphere(pos: THREE.Vector3, r: number, color: number): THREE.Mesh {
  const m = new THREE.Mesh(new THREE.SphereGeometry(r, 6, 6), dbgMat(color));
  m.position.copy(pos);
  return m;
}

function dbgLine(from: THREE.Vector3, to: THREE.Vector3, color: number): THREE.Mesh | null {
  return makeCylinder(to, from, 0.12, 0.12, 5, dbgMat(color));
}

// ── Main ───────────────────────────────────────────────────────────────────────

/**
 * Generate tree-style support structures for a list of overhang faces.
 *
 * Algorithm:
 *  1. Extract support tip positions from overhang face centroids
 *  2. Cluster them by XZ proximity → each cluster gets one trunk
 *  3. Build a vertical trunk from Y=0 to the cluster's max-Y tip
 *  4. For each tip in the cluster, build a tapered branch from trunk to tip
 *  5. Add small spherical contact caps at each tip
 *
 * @param overhangFaces   Output of detectOverhangFaces()
 * @param modelMesh       Optional — used for coarse collision rejection
 * @param options         Geometry / material overrides
 */
export function generateTreeSupports(
  overhangFaces: OverhangFace[],
  modelMesh?:    THREE.Mesh,
  options:       TreeSupportOptions = {},
): THREE.Group {
  const {
    trunkRadius       = 1.2,
    branchRadius      = 0.7,
    tipRadius         = 0.3,
    maxBranchAngleDeg = 45,
    clusterDistance   = 8,
    radialSegments    = 8,
    material          = defaultMaterial(),
    debug             = false,
    baseFlare         = true,
    baseFlareRadius   = 2.2,
    baseFlareHeight   = 1.5,
    minimumBranchThickness   = 0.8,
    maximumUnsupportedLength = 40,
    supportCoverageRadius,
  } = options;

  // Effective radii after applying minimumBranchThickness floor
  const minR          = minimumBranchThickness / 2;
  const effBranchR    = Math.max(branchRadius, minR);
  const effTipR       = Math.max(tipRadius,    minR);

  const group = new THREE.Group();
  group.name  = "tree-supports";

  // Debug group — attached as named child only when debug:true; never present otherwise
  const dbg = debug ? new THREE.Group() : null;
  if (dbg) dbg.name = "__debug__";

  if (!overhangFaces.length) {
    if (dbg) group.add(dbg);
    return group;
  }

  // 1. Collect + deduplicate tip positions.
  //    Dedup spacing = max(tipDiam, 80% of branchRadius) — suppresses dense areas.
  const rawTips = overhangFaces.map(f => f.center.clone());
  rawTips.sort((a, b) => b.y - a.y);
  // Wider dedup: one tip per coverage radius suppresses overhang load redundancy
  const coverageR    = supportCoverageRadius ?? (clusterDistance / 2);
  const dedupSpacing = Math.max(effTipR * 3, effBranchR * 1.4, coverageR);
  const tips = deduplicateTips(rawTips, dedupSpacing);

  // Debug: coverage visualization — kept tips (lime) vs removed redundant tips (gray)
  // Disks on the bed show the effective XZ coverage radius of each kept tip.
  if (dbg) {
    const keptSet = new Set(tips); // same object refs — safe for Set lookup
    const diskMat = new THREE.MeshBasicMaterial({
      color: 0x00ff44, transparent: true, opacity: 0.12, depthWrite: false, side: THREE.DoubleSide,
    });
    for (const t of rawTips) {
      if (keptSet.has(t)) {
        dbg.add(dbgSphere(t, effTipR * 0.9, 0x00ff88));                           // lime: kept tip
        const disk = new THREE.Mesh(
          new THREE.CylinderGeometry(dedupSpacing, dedupSpacing, 0.05, 20),
          diskMat,
        );
        disk.position.set(t.x, 0.03, t.z);                                        // projected to bed
        dbg.add(disk);
      } else {
        dbg.add(dbgSphere(t, effTipR * 0.5, 0x555555));                           // gray: removed redundant
      }
    }
  }

  // 2. Cluster by XZ proximity, then merge surviving nearby clusters
  const clusters = mergeClusters(
    clusterPoints(tips, clusterDistance),
    clusterDistance * 0.6,   // more aggressive merge → fewer trunks
  );

  for (const cluster of clusters) {
    const { points } = cluster;

    // Trunk base — XZ position weighted by tip height so tall overhangs
    // pull the trunk toward the area needing the most support.
    let wx = 0, wz = 0, wSum = 0;
    for (const p of points) { const w = p.y + 0.1; wx += p.x * w; wz += p.z * w; wSum += w; }
    const trunkBase = new THREE.Vector3(wx / wSum, 0, wz / wSum);

    // Debug: cluster centroid marker (yellow)
    if (dbg) dbg.add(dbgSphere(trunkBase, 1.0, 0xffff00));

    // Trunk top = highest tip in cluster
    const trunkTopY = Math.max(...points.map(p => p.y));
    const trunkTop  = new THREE.Vector3(trunkBase.x, trunkTopY, trunkBase.z);

    if (trunkTopY < 0.5) continue;
    if (!isValidVec3(trunkBase) || !isValidVec3(trunkTop)) continue;

    // 3. Trunk — shorten if model obstructs the vertical path
    let effectiveTrunkTopY = trunkTopY;
    if (modelMesh) {
      const hitDist = raycastBranchPath(trunkBase, trunkTop, modelMesh, 0.01);
      if (hitDist !== null) {
        effectiveTrunkTopY = Math.min(trunkTopY, hitDist - trunkRadius);
        // Debug: trunk collision hit point (orange)
        if (dbg) dbg.add(dbgSphere(trunkBase.clone().setY(hitDist), 0.6, 0xff8800));
      }
    }
    const effectiveTrunkTop = new THREE.Vector3(trunkBase.x, effectiveTrunkTopY, trunkBase.z);
    if (effectiveTrunkTopY < 0.5) continue;

    const trunk = makeCylinder(effectiveTrunkTop, trunkBase, trunkRadius * 0.8, trunkRadius, radialSegments, material);
    if (trunk) group.add(trunk);

    // Base flare — short cone at Y=0 for better bed adhesion
    if (baseFlare) {
      const flareTopY = Math.min(baseFlareHeight, Math.max(0.4, effectiveTrunkTopY * 0.2));
      const flareTop  = trunkBase.clone().setY(flareTopY);
      const flare     = makeCylinder(flareTop, trunkBase, trunkRadius, trunkRadius * baseFlareRadius, radialSegments, material);
      if (flare) group.add(flare);
    }

    // Debug: trunk path line (cyan)
    if (dbg) { const l = dbgLine(trunkBase, effectiveTrunkTop, 0x00ffff); if (l) dbg.add(l); }

    // 4. Branches — deduplicate within cluster by XZ proximity, then one branch per tip
    const intraDedup = Math.max(effBranchR * 2.0, trunkRadius * 0.9);
    const keptPoints = deduplicateTips(
      [...points].sort((a, b) => b.y - a.y), // highest-priority tips first
      intraDedup,
    );
    for (const tip of keptPoints) {
      if (!isValidVec3(tip)) continue;

      // Skip tips inside model
      if (modelMesh && isInsideMesh(tip, modelMesh)) {
        if (dbg) dbg.add(dbgSphere(tip, 0.5, 0xff0000)); // rejected tip: red
        continue;
      }

      const branchBase = clampBranchBase(tip, trunkBase, maxBranchAngleDeg);

      if (!isValidVec3(branchBase)) continue;
      if (branchBase.y < 0)         continue;

      // Skip branch base inside model
      if (modelMesh && isInsideMesh(branchBase, modelMesh)) {
        if (dbg) dbg.add(dbgSphere(branchBase, 0.5, 0xff0000)); // rejected base: red
        continue;
      }

      // Angle sanity: branch must rise upward — downward paths are never printable
      if (tip.y < branchBase.y - 0.1) {
        if (dbg) dbg.add(dbgSphere(tip, 0.4, 0xff6600)); // downward rejection: amber
        continue;
      }

      // Raycast along branch path — shorten on collision, skip if too short.
      // Pull back by exactly effTipR so the contact sphere just kisses the surface.
      let effectiveTip = tip.clone();
      if (modelMesh) {
        const hitDist = raycastBranchPath(branchBase, tip, modelMesh);
        if (hitDist !== null) {
          const branchDir = new THREE.Vector3().subVectors(tip, branchBase).normalize();
          // Debug: branch collision hit point (orange)
          if (dbg) dbg.add(dbgSphere(branchBase.clone().addScaledVector(branchDir, hitDist), 0.5, 0xff8800));
          const shortLen = hitDist - effTipR; // contact sanity: stop one radius short of surface
          if (shortLen < 1.0) {
            if (dbg) dbg.add(dbgSphere(tip, 0.4, 0xff0000)); // too-short rejection: red
            continue;
          }
          effectiveTip = branchBase.clone().addScaledVector(branchDir, shortLen);
        }
      }

      const branchLen = effectiveTip.distanceTo(branchBase);
      if (branchLen < 1.0) {
        if (dbg) dbg.add(dbgSphere(tip, 0.4, 0xff0000)); // too-short rejection: red
        continue;
      }

      // Slenderness check: skip branches too long for their minimum cross-section.
      // Grounded trunks are exempt — only cantilevered branches are checked here.
      if (branchLen > maximumUnsupportedLength) {
        if (dbg) dbg.add(dbgSphere(tip, 0.5, 0xff00ff)); // slenderness rejection: magenta
        continue;
      }

      // Two-segment elbow: base→elbow (thick) + elbow→tip (thin) + joint sphere
      // Bow magnitude scales with horizontal reach so angled branches arc naturally
      const horizDist2D = Math.hypot(
        effectiveTip.x - branchBase.x,
        effectiveTip.z - branchBase.z,
      );
      const elbowT = 0.60;
      const midR   = effBranchR + (effTipR - effBranchR) * elbowT;
      const elbow  = new THREE.Vector3().lerpVectors(branchBase, effectiveTip, elbowT);
      elbow.y     += Math.min(horizDist2D * 0.15, branchLen * 0.12); // horizon-weighted bow

      // Island/floating invariant: every branch attaches to a trunk that is
      // grounded at Y=0 via trunkBase — floating geometry is impossible here.
      const seg1  = makeCylinder(elbow,       branchBase, midR,      effBranchR, radialSegments, material);
      const seg2  = makeCylinder(effectiveTip, elbow,     effTipR,   midR,       radialSegments, material);
      const joint = makeSphere(elbow, midR * 1.05, material);
      if (seg1)  group.add(seg1);
      if (seg2)  group.add(seg2);
      if (joint) group.add(joint);

      // Debug: two-segment branch path (magenta)
      if (dbg) {
        const l1 = dbgLine(branchBase, elbow,       0xff00ff);
        const l2 = dbgLine(elbow,      effectiveTip, 0xff00ff);
        if (l1) dbg.add(l1);
        if (l2) dbg.add(l2);
      }

      // Contact sanity: cap sphere must not exceed branch radius (no oversized contacts)
      const capR = Math.min(effTipR * 1.1, effBranchR * 0.8);
      const cap  = makeSphere(effectiveTip, capR, material);
      if (cap) group.add(cap);
    }
  }

  if (dbg) group.add(dbg);
  return group;
}
