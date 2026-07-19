import * as THREE from "three";
import { RED_MATERIAL, MeshBuild, addBox, addRing } from "./GeometryUtils";
import { BoxSettings } from "./Presets";
import { buildDividers } from "./DividerBuilder";
import { buildHinges } from "./HingeBuilder";
import { buildLatch } from "./LatchBuilder";

export function buildBox(settings: BoxSettings): MeshBuild {
  const group = new THREE.Group();
  group.name = "Box";
  const meshes: THREE.Mesh[] = [];
  const wall = settings.wall;
  const bodyH = settings.height;

  addBox(group, meshes, [settings.length, settings.bottom, settings.width], [0, settings.bottom / 2, 0], RED_MATERIAL, "box-bottom", settings.radius);
  addRing(
    group,
    meshes,
    [settings.length, Math.max(wall, bodyH - settings.bottom), settings.width],
    wall,
    [0, settings.bottom, 0],
    RED_MATERIAL,
    "box-wall-shell",
    settings.radius,
  );

  if (settings.feet) {
    const foot = Math.max(6, settings.radius * 0.9);
    const positions: [number, number, number][] = [
      [-settings.length / 2 + foot, -1.2, -settings.width / 2 + foot],
      [settings.length / 2 - foot, -1.2, -settings.width / 2 + foot],
      [-settings.length / 2 + foot, -1.2, settings.width / 2 - foot],
      [settings.length / 2 - foot, -1.2, settings.width / 2 - foot],
    ];
    positions.forEach((pos) => addBox(group, meshes, [foot, 2.4, foot], pos, RED_MATERIAL, "foot", 1));
  }

  if (settings.ventilation) {
    for (let i = -2; i <= 2; i += 1) {
      addBox(group, meshes, [2, bodyH * 0.35, 1.2], [i * 7, bodyH * 0.52, -settings.width / 2 - 0.6], RED_MATERIAL, "vent-preview-rib", 0.2);
    }
  }

  if (settings.labelHolder) {
    addBox(group, meshes, [settings.length * 0.38, 1.4, 2.2], [0, bodyH * 0.55, -settings.width / 2 - 2], RED_MATERIAL, "label-holder", 0.5);
  }

  if (settings.cablePass) {
    addBox(group, meshes, [14, 3, 2.4], [settings.length / 2 - wall - 10, wall + 2, -settings.width / 2 - 1.6], RED_MATERIAL, "cable-pass-relief-preview", 0.8);
  }

  const dividers = buildDividers(settings);
  group.add(dividers.group);
  meshes.push(...dividers.meshes);

  const hinges = buildHinges(settings, "box");
  group.add(hinges.group);
  meshes.push(...hinges.meshes);

  const latch = buildLatch(settings, "box");
  group.add(latch.group);
  meshes.push(...latch.meshes);

  return { group, meshes };
}
