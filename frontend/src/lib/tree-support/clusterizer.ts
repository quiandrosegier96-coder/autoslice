/**
 * AutoSlice - Overhang face sampler.
 *
 * A real slicer does not create one support target for a whole connected
 * overhang island. It samples many contact points across broad unsupported
 * areas, then lets nearby points share trunks. This module follows that model:
 * one occupied grid cell becomes one OverhangCluster.
 */

import * as THREE from "three";
import type { OverhangFace, OverhangCluster, SupportConfig } from "./types";

export function clusterOverhangs(
  faces:  OverhangFace[],
  config: SupportConfig,
): OverhangCluster[] {
  if (faces.length === 0) return [];

  const cell = Math.max(config.clusterCellMm, 1.0);
  const cellToFaces = new Map<string, number[]>();

  faces.forEach((face, index) => {
    const gx = Math.floor(face.centroid.x / cell);
    const gy = Math.floor(face.centroid.y / cell);
    const gz = Math.floor(face.centroid.z / cell);
    const key = `${gx},${gy},${gz}`;
    if (!cellToFaces.has(key)) cellToFaces.set(key, []);
    cellToFaces.get(key)!.push(index);
  });

  const clusters: OverhangCluster[] = [];
  let clusterId = 0;

  for (const faceIndices of cellToFaces.values()) {
    const clusterFaces = faceIndices.map((i) => faces[i]);
    const centroid = new THREE.Vector3();
    const box = new THREE.Box3();
    let totalArea = 0;

    for (const face of clusterFaces) {
      centroid.addScaledVector(face.centroid, face.area);
      box.expandByPoint(face.centroid);
      totalArea += face.area;
    }
    centroid.divideScalar(totalArea || 1);

    const avgNormal = new THREE.Vector3();
    for (const face of clusterFaces) avgNormal.add(face.normal);
    avgNormal.normalize();

    clusters.push({
      id: clusterId++,
      centroid,
      area: totalArea,
      boundingBox: box,
      faces: clusterFaces,
      tipPosition: centroid.clone().addScaledVector(avgNormal, config.zDistanceMm),
    });
  }

  return clusters.sort((a, b) => b.area - a.area);
}

/**
 * Group contact targets by XZ proximity. Each group shares one trunk, while the
 * individual clusters remain separate tip/contact points.
 */
export function groupClustersByXZ(
  clusters: OverhangCluster[],
  radiusMm: number,
): OverhangCluster[][] {
  if (clusters.length === 0) return [];

  const used = new Array(clusters.length).fill(false);
  const groups: OverhangCluster[][] = [];

  for (let i = 0; i < clusters.length; i++) {
    if (used[i]) continue;
    const group = [clusters[i]];
    used[i] = true;

    for (let j = i + 1; j < clusters.length; j++) {
      if (used[j]) continue;
      const dx = clusters[i].centroid.x - clusters[j].centroid.x;
      const dz = clusters[i].centroid.z - clusters[j].centroid.z;
      if (Math.sqrt(dx * dx + dz * dz) <= radiusMm) {
        group.push(clusters[j]);
        used[j] = true;
      }
    }

    groups.push(group);
  }

  return groups;
}
