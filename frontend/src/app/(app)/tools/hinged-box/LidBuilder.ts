import * as THREE from "three";
import { LID_MATERIAL, MeshBuild, addBox } from "./GeometryUtils";
import { BoxSettings } from "./Presets";
import { buildHinges } from "./HingeBuilder";
import { buildLatch } from "./LatchBuilder";

export function buildLid(settings: BoxSettings): MeshBuild {
  const group = new THREE.Group();
  group.name = "Lid";
  const meshes: THREE.Mesh[] = [];
  const overhang = settings.lidStyle === "overhang" ? settings.wall * 2 : 0;
  const inset = settings.lidStyle === "inset" ? settings.tolerance * 2 : 0;
  const lipHeight = settings.lidStyle === "lip" || settings.lidStyle === "inset" ? settings.lidLipHeight : 0;
  const length = settings.length + overhang - inset;
  const width = settings.width + overhang - inset;

  addBox(group, meshes, [length, settings.lidThickness, width], [0, settings.lidThickness / 2, 0], LID_MATERIAL, "lid-top", settings.radius);

  if (lipHeight > 0) {
    const lipL = settings.length - settings.wall * 2 - settings.tolerance * 2;
    const lipW = settings.width - settings.wall * 2 - settings.tolerance * 2;
    addBox(group, meshes, [lipL, lipHeight, settings.wall], [0, -lipHeight / 2, lipW / 2], LID_MATERIAL, "lid-back-lip", Math.min(settings.radius, settings.wall));
    addBox(group, meshes, [lipL, lipHeight, settings.wall], [0, -lipHeight / 2, -lipW / 2], LID_MATERIAL, "lid-front-lip", Math.min(settings.radius, settings.wall));
    addBox(group, meshes, [settings.wall, lipHeight, lipW], [-lipL / 2, -lipHeight / 2, 0], LID_MATERIAL, "lid-left-lip", Math.min(settings.radius, settings.wall));
    addBox(group, meshes, [settings.wall, lipHeight, lipW], [lipL / 2, -lipHeight / 2, 0], LID_MATERIAL, "lid-right-lip", Math.min(settings.radius, settings.wall));
  }

  if (settings.ribs) {
    addBox(group, meshes, [length * 0.72, settings.lidThickness * 0.55, settings.wall], [0, -settings.lidThickness * 0.2, 0], LID_MATERIAL, "lid-cross-rib-x", 0.2);
    addBox(group, meshes, [settings.wall, settings.lidThickness * 0.55, width * 0.72], [0, -settings.lidThickness * 0.2, 0], LID_MATERIAL, "lid-cross-rib-z", 0.2);
  }

  if (settings.stackable) {
    addBox(group, meshes, [length * 0.72, 1.2, width * 0.72], [0, settings.lidThickness + 0.6, 0], LID_MATERIAL, "stacking-ledge", Math.max(0, settings.radius - 2));
  }

  if (settings.textTop.trim()) {
    const textWidth = Math.min(length * 0.64, Math.max(18, settings.textTop.length * settings.textSize * 0.48));
    const textDepth = Math.max(0.2, settings.textDepth);
    addBox(
      group,
      meshes,
      [textWidth, textDepth, settings.textSize * 0.45],
      [0, settings.lidThickness + (settings.textRaised ? textDepth / 2 : 0.1), -width * 0.08],
      LID_MATERIAL,
      settings.textRaised ? "raised-text-plaque" : "engraved-text-preview",
      0.6,
    );
  }

  const hinges = buildHinges(settings, "lid");
  group.add(hinges.group);
  meshes.push(...hinges.meshes);

  const latch = buildLatch(settings, "lid");
  group.add(latch.group);
  meshes.push(...latch.meshes);

  return { group, meshes };
}
