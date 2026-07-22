import * as THREE from "three";
import { ACCENT_MATERIAL, MeshBuild, addBox } from "./GeometryUtils";
import { BoxSettings } from "./Presets";

export function buildDividers(settings: BoxSettings): MeshBuild {
  const group = new THREE.Group();
  const meshes: THREE.Mesh[] = [];
  if (settings.dividerMode === "none") return { group, meshes };

  const innerLength = settings.length - settings.wall * 2 - settings.tolerance;
  const innerWidth = settings.width - settings.wall * 2 - settings.tolerance;
  const topClearance = Math.max(settings.wall * 3.5, settings.lidLipHeight + settings.tolerance + settings.nozzle + 2, 8);
  const dividerTop = Math.max(settings.bottom + 4, settings.height - topClearance);
  const h = Math.max(4, dividerTop - settings.bottom);
  const y = settings.bottom + h / 2;
  const t = settings.dividerThickness;

  if (settings.dividerMode === "horizontal" || settings.dividerMode === "grid") {
    for (let row = 1; row < settings.dividerRows; row += 1) {
      const z = -innerWidth / 2 + (innerWidth / settings.dividerRows) * row;
      addBox(group, meshes, [innerLength, h, t], [0, y, z], ACCENT_MATERIAL, "horizontal-divider", 0);
    }
  }

  if (settings.dividerMode === "vertical" || settings.dividerMode === "grid") {
    for (let col = 1; col < settings.dividerColumns; col += 1) {
      const x = -innerLength / 2 + (innerLength / settings.dividerColumns) * col;
      addBox(group, meshes, [t, h, innerWidth], [x, y, 0], ACCENT_MATERIAL, "vertical-divider", 0);
    }
  }

  return { group, meshes };
}
