import * as THREE from "three";
import { repairGeometry } from "./repairGeometry";

// ── Constants ──────────────────────────────────────────────────────────────────

const ANGLE_STEP_RAD     = Math.PI / 4;             // 45° steps → 64 candidates
const OVERHANG_COS       = Math.cos(Math.PI / 4);   // 45° overhang threshold
const WEIGHT_HEIGHT      = 0.4;                      // prefer low profile
const WEIGHT_OVERHANG    = 0.6;                      // prefer minimal overhang

// ── Internal types ─────────────────────────────────────────────────────────────

type Candidate = {
  rotation:     THREE.Euler;
  height:       number;
  overhangArea: number;
  score:        number;
};

// ── Overhang area evaluation ───────────────────────────────────────────────────

function evaluateGeometry(
  geometry: THREE.BufferGeometry,
  rotation: THREE.Euler,
): { height: number; overhangArea: number } {
  const geo = geometry.clone();
  geo.applyMatrix4(new THREE.Matrix4().makeRotationFromEuler(rotation));
  geo.computeBoundingBox();

  const bb     = geo.boundingBox!;
  const height = bb.max.y - bb.min.y;

  const pos   = geo.attributes.position;
  const index = geo.index;
  const up    = new THREE.Vector3(0, 1, 0);

  const a  = new THREE.Vector3();
  const b  = new THREE.Vector3();
  const c  = new THREE.Vector3();
  const ab = new THREE.Vector3();
  const ac = new THREE.Vector3();
  const n  = new THREE.Vector3();

  let overhangArea = 0;
  const faceCount  = index ? index.count / 3 : pos.count / 3;

  for (let i = 0; i < faceCount; i++) {
    const i0 = index ? index.getX(i * 3)     : i * 3;
    const i1 = index ? index.getX(i * 3 + 1) : i * 3 + 1;
    const i2 = index ? index.getX(i * 3 + 2) : i * 3 + 2;

    a.fromBufferAttribute(pos, i0);
    b.fromBufferAttribute(pos, i1);
    c.fromBufferAttribute(pos, i2);

    ab.subVectors(b, a);
    ac.subVectors(c, a);
    n.crossVectors(ab, ac);

    const area = n.length() * 0.5;
    n.normalize();

    if (n.dot(up) < -OVERHANG_COS) {
      overhangArea += area;
    }
  }

  return { height, overhangArea };
}

// ── Candidate generation ───────────────────────────────────────────────────────

function generateCandidates(): THREE.Euler[] {
  const candidates: THREE.Euler[] = [];
  for (let x = 0; x < Math.PI * 2 - 1e-6; x += ANGLE_STEP_RAD) {
    for (let y = 0; y < Math.PI * 2 - 1e-6; y += ANGLE_STEP_RAD) {
      candidates.push(new THREE.Euler(x, y, 0));
    }
  }
  return candidates;
}

// ── Public API ─────────────────────────────────────────────────────────────────

/**
 * Rotate the geometry to the orientation that minimises print height and
 * overhang area.  Returns a new repaired BufferGeometry with the rotation
 * baked in.  The input geometry is not mutated.
 */
export function autoOrientGeometry(
  inputGeometry: THREE.BufferGeometry,
): THREE.BufferGeometry {
  const candidates = generateCandidates();

  // First pass — collect raw metrics
  const raw: Omit<Candidate, "score">[] = candidates.map((rotation) => {
    const { height, overhangArea } = evaluateGeometry(inputGeometry, rotation);
    return { rotation, height, overhangArea };
  });

  // Normalisation ranges
  const maxHeight   = Math.max(...raw.map((r) => r.height),   1e-9);
  const maxOverhang = Math.max(...raw.map((r) => r.overhangArea), 1e-9);

  // Second pass — score and pick best
  let best: Candidate | null = null;

  for (const r of raw) {
    const score =
      WEIGHT_HEIGHT   * (r.height       / maxHeight) +
      WEIGHT_OVERHANG * (r.overhangArea / maxOverhang);

    if (best === null || score < best.score) {
      best = { ...r, score };
    }
  }

  // Apply winning rotation and return clean geometry
  const geometry = inputGeometry.clone();
  geometry.applyMatrix4(
    new THREE.Matrix4().makeRotationFromEuler(best!.rotation),
  );

  return repairGeometry(geometry);
}
