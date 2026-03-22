import * as THREE from "three";
import type { OverhangFace } from "./detectOverhangFaces";

type SupportOptions = {
  pillarRadius?: number;
  minHeight?:   number;
  sampleStep?:  number;
  material?:    THREE.Material;
};

export function generateBasicSupports(
  overhangFaces: OverhangFace[],
  options: SupportOptions = {},
): THREE.Group {
  const {
    pillarRadius = 0.8,
    minHeight    = 1.5,
    sampleStep   = 6,
    material     = new THREE.MeshStandardMaterial({
      color:       0x999999,
      transparent: true,
      opacity:     0.7,
    }),
  } = options;

  const supportsGroup = new THREE.Group();

  for (let i = 0; i < overhangFaces.length; i += sampleStep) {
    const point = overhangFaces[i].center;

    const height = point.y;
    if (height < minHeight) continue;

    const geo    = new THREE.CylinderGeometry(pillarRadius, pillarRadius, height, 10);
    const pillar = new THREE.Mesh(geo, material);
    pillar.position.set(point.x, height / 2, point.z);

    supportsGroup.add(pillar);
  }

  return supportsGroup;
}
