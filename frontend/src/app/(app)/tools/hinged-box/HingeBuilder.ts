import * as THREE from "three";
import { ACCENT_MATERIAL, HINGE_MATERIAL, MeshBuild, cylinderBetween, makeMesh } from "./GeometryUtils";
import { BoxSettings, effectiveHingeClearance, pinDiameter } from "./Presets";

function hingeSegments(settings: BoxSettings) {
  if (settings.hingeMode === "none") return [];
  const count = settings.hingeMode === "two" ? 2 : settings.hingeMode === "three" ? 3 : 1;
  const total = settings.length * 0.74;
  if (settings.hingeMode === "continuous") return [{ center: 0, length: total, owner: "box" as const }];
  const segmentLength = total / (count * 1.65);
  const gap = count === 1 ? 0 : (total - segmentLength * count) / (count - 1);
  return Array.from({ length: count }, (_, index) => ({
    center: -total / 2 + segmentLength / 2 + index * (segmentLength + gap),
    length: segmentLength,
    owner: index % 2 === 0 ? "box" as const : "lid" as const,
  }));
}

export function buildHinges(settings: BoxSettings, forPart: "box" | "lid"): MeshBuild {
  const group = new THREE.Group();
  const meshes: THREE.Mesh[] = [];
  if (settings.hingeMode === "none") return { group, meshes };

  const barrelRadius = settings.hingeDiameter / 2;
  const pinRadius = pinDiameter(settings.pinType) / 2;
  const clearance = effectiveHingeClearance(settings);
  const y = forPart === "box" ? settings.height - barrelRadius * 0.9 : settings.lidThickness + barrelRadius * 0.2;
  const z = settings.width / 2 + barrelRadius * 0.62;

  hingeSegments(settings)
    .filter((segment) => settings.hingeMode === "continuous" || segment.owner === forPart)
    .forEach((segment) => {
      const barrel = cylinderBetween(
        new THREE.Vector3(segment.center - segment.length / 2, y, z),
        new THREE.Vector3(segment.center + segment.length / 2, y, z),
        barrelRadius,
        HINGE_MATERIAL,
        `${forPart}-hinge-barrel`,
      );
      group.add(barrel);
      meshes.push(barrel);

      const bore = cylinderBetween(
        new THREE.Vector3(segment.center - segment.length / 2 - 0.1, y, z),
        new THREE.Vector3(segment.center + segment.length / 2 + 0.1, y, z),
        pinRadius + clearance,
        ACCENT_MATERIAL,
        `${forPart}-hinge-pin-clearance-preview`,
        18,
      );
      bore.material = ACCENT_MATERIAL.clone();
      (bore.material as THREE.MeshStandardMaterial).transparent = true;
      (bore.material as THREE.MeshStandardMaterial).opacity = 0.22;
      group.add(bore);

      const tabGeometry = new THREE.BoxGeometry(segment.length, barrelRadius * 1.6, settings.wall * 1.4);
      const tab = makeMesh(tabGeometry, HINGE_MATERIAL, `${forPart}-hinge-leaf`);
      tab.position.set(segment.center, forPart === "box" ? y - barrelRadius : y + barrelRadius, settings.width / 2 + settings.wall * 0.25);
      group.add(tab);
      meshes.push(tab);
    });

  return { group, meshes };
}
