import * as THREE from "three";
import type { OverhangFace } from "./detectOverhangFaces";

// ── Constants ──────────────────────────────────────────────────────────────────

const DOWN             = new THREE.Vector3(0, -1, 0);
const RAY_ORIGIN_LIFT  = 0.01;   // mm — lift ray origin off surface to avoid self-hit
const MIN_PILLAR_HEIGHT = 0.5;   // mm — skip trivially short pillars
const SELF_HIT_EPSILON  = 0.05;  // mm — hits closer than this are self-intersection

// ── Default material ───────────────────────────────────────────────────────────

function defaultMaterial(): THREE.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({
    color:       0x888888,
    transparent: true,
    opacity:     0.65,
    depthWrite:  false,
  });
}

// ── Types ──────────────────────────────────────────────────────────────────────

export type SupportOptions = {
  pillarRadius?: number;   // mm, default 0.8
  radialSegments?: number; // cylinder segments, default 8
  material?: THREE.Material;
};

export type SupportResult = {
  group:       THREE.Group;
  pillarCount: number;
};

// ── Raycast helper ─────────────────────────────────────────────────────────────

/**
 * Cast a ray downward from `origin` against `meshes`.
 * Returns the Y coordinate of the first valid hit, or 0 (bed) if nothing hit.
 * Ignores hits within SELF_HIT_EPSILON of the origin (self-intersection).
 */
function raycastFloor(
  origin:  THREE.Vector3,
  meshes:  THREE.Mesh[],
): number {
  const raycaster = new THREE.Raycaster();
  const rayOrigin = origin.clone();
  rayOrigin.y    -= RAY_ORIGIN_LIFT;

  raycaster.set(rayOrigin, DOWN);

  const hits = raycaster.intersectObjects(meshes, false);

  for (const hit of hits) {
    if (hit.distance > SELF_HIT_EPSILON) {
      return hit.point.y;
    }
  }

  return 0; // nothing hit — pillar reaches the bed
}

// ── Pillar builder ─────────────────────────────────────────────────────────────

function buildPillar(
  topY:    number,
  bottomY: number,
  x:       number,
  z:       number,
  radius:  number,
  segments: number,
  material: THREE.Material,
): THREE.Mesh {
  const height = topY - bottomY;
  const geo    = new THREE.CylinderGeometry(radius, radius * 1.1, height, segments, 1);
  const mesh   = new THREE.Mesh(geo, material);
  mesh.position.set(x, bottomY + height / 2, z);
  return mesh;
}

// ── Public API ─────────────────────────────────────────────────────────────────

/**
 * Generate vertical support pillars for a list of overhang faces.
 *
 * Each pillar is ray-cast downward from the face centroid against the model
 * mesh to find the correct floor Y.  Pillars that would start inside the model
 * or are shorter than MIN_PILLAR_HEIGHT are discarded.
 *
 * @param overhangFaces  Output of detectOverhangFaces()
 * @param modelMesh      The model mesh used for downward raycasting
 * @param options        Pillar geometry / material overrides
 */
export function generateSupports(
  overhangFaces: OverhangFace[],
  modelMesh:     THREE.Mesh,
  options:       SupportOptions = {},
): SupportResult {
  const {
    pillarRadius   = 0.8,
    radialSegments = 8,
    material       = defaultMaterial(),
  } = options;

  const group  = new THREE.Group();
  group.name   = "supports";
  const meshes = [modelMesh];

  for (const face of overhangFaces) {
    const topY    = face.center.y;
    const bottomY = raycastFloor(face.center, meshes);

    const height = topY - bottomY;
    if (height < MIN_PILLAR_HEIGHT) continue;

    const pillar = buildPillar(
      topY, bottomY,
      face.center.x, face.center.z,
      pillarRadius, radialSegments,
      material,
    );

    group.add(pillar);
  }

  return { group, pillarCount: group.children.length };
}
