import * as THREE from "three";
import { ACCENT_MATERIAL, MeshBuild, addBox, cylinderBetween } from "./GeometryUtils";
import { BoxSettings } from "./Presets";

export function buildLatch(settings: BoxSettings, forPart: "box" | "lid"): MeshBuild {
  const group = new THREE.Group();
  const meshes: THREE.Mesh[] = [];
  if (settings.latchType === "none") return { group, meshes };

  const frontZ = -settings.width / 2;
  const y = forPart === "box" ? settings.height - settings.wall * 1.2 : settings.lidThickness / 2;

  if (settings.latchType === "snap" || settings.latchType === "doubleSnap") {
    const count = settings.latchType === "doubleSnap" ? 2 : 1;
    const spacing = settings.length * 0.36;
    for (let i = 0; i < count; i += 1) {
      const x = count === 1 ? 0 : -spacing / 2 + i * spacing;
      if (forPart === "lid") {
        addBox(group, meshes, [12, settings.lidThickness, 3.2], [x, y - 0.2, frontZ - 2.2], ACCENT_MATERIAL, "snap-hook", 0.3);
      } else {
        addBox(group, meshes, [14, settings.wall * 1.2, 2.6], [x, y, frontZ - 1.6], ACCENT_MATERIAL, "snap-catch", 0.2);
      }
    }
  }

  if (settings.latchType === "lip") {
    addBox(
      group,
      meshes,
      [settings.length * 0.42, settings.lidThickness, 3],
      [0, y, frontZ - 2],
      ACCENT_MATERIAL,
      forPart === "lid" ? "front-lip" : "lip-seat",
      0.3,
    );
  }

  if (settings.latchType === "slide") {
    addBox(group, meshes, [settings.length * 0.5, 2.4, 4], [0, y, frontZ - 2.2], ACCENT_MATERIAL, `${forPart}-slide-rail`, 0.3);
  }

  if (settings.latchType === "magnet") {
    const count = Math.max(1, settings.magnetCount);
    const span = Math.min(settings.length * 0.62, count * settings.magnetDiameter * 2.4);
    for (let i = 0; i < count; i += 1) {
      const x = count === 1 ? 0 : -span / 2 + (span / (count - 1)) * i;
      const pocket = cylinderBetween(
        new THREE.Vector3(x, y - settings.magnetHeight / 2, frontZ - settings.wall * 0.6),
        new THREE.Vector3(x, y + settings.magnetHeight / 2, frontZ - settings.wall * 0.6),
        settings.magnetDiameter / 2 + settings.tolerance,
        ACCENT_MATERIAL,
        `${forPart}-magnet-pocket-preview`,
      );
      (pocket.material as THREE.MeshStandardMaterial).transparent = true;
      (pocket.material as THREE.MeshStandardMaterial).opacity = 0.28;
      group.add(pocket);
    }
  }

  return { group, meshes };
}
