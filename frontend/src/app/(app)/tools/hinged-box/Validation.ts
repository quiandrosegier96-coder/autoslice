import { BoxSettings, effectiveHingeClearance, pinDiameter } from "./Presets";

export type ValidationIssue = {
  severity: "error" | "warning" | "info";
  message: string;
};

export function validateSettings(settings: BoxSettings): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const minWall = settings.nozzle * 2;
  const innerLength = settings.length - settings.wall * 2;
  const innerWidth = settings.width - settings.wall * 2;
  const pin = pinDiameter(settings.pinType);
  const hingeClearance = effectiveHingeClearance(settings);

  if (settings.wall < minWall) {
    issues.push({
      severity: "error",
      message: `Wanddikte te dun voor ${settings.nozzle} mm nozzle. Gebruik minstens ${minWall.toFixed(1)} mm.`,
    });
  }
  if (settings.bottom < settings.nozzle * 2) {
    issues.push({ severity: "warning", message: "Bodemdikte is dun; verhoog voor stijvere prints." });
  }
  if (settings.lidThickness < settings.nozzle * 2) {
    issues.push({ severity: "warning", message: "Dekseldikte is dun; kliksluitingen kunnen zwak worden." });
  }
  if (innerLength < 20 || innerWidth < 20) {
    issues.push({ severity: "error", message: "Binnenruimte wordt te klein door wanddikte/radius." });
  }
  if (settings.radius > Math.min(settings.length, settings.width) / 2 - settings.wall) {
    issues.push({ severity: "error", message: "Hoekradius is groter dan de beschikbare buitenmaat." });
  }
  if (settings.hingeMode !== "none") {
    if (settings.hingeDiameter < pin + hingeClearance * 2 + settings.nozzle) {
      issues.push({ severity: "error", message: "Scharnier te klein voor gekozen pen/nozzle." });
    }
    if (settings.hingeDiameter > settings.height * 0.45) {
      issues.push({ severity: "warning", message: "Scharnierdiameter is groot tegenover de dooshoogte." });
    }
  }
  if (settings.latchType === "magnet" && settings.magnetDiameter + settings.tolerance * 2 > settings.wall * 5) {
    issues.push({ severity: "warning", message: "Magneetuitsparing vraagt veel materiaal; verhoog wanddikte of kies kleinere magneten." });
  }
  if (settings.dividerMode !== "none" && settings.dividerThickness < settings.nozzle * 2) {
    issues.push({ severity: "warning", message: "Verdelers zijn dun voor de gekozen nozzle." });
  }
  if (!issues.length) {
    issues.push({ severity: "info", message: "Ontwerp is printbaar met de huidige instellingen." });
  }
  return issues;
}

export function autoCorrect(settings: BoxSettings): BoxSettings {
  const minWall = Math.max(settings.nozzle * 2, 0.8);
  const corrected = { ...settings };
  corrected.wall = Math.max(corrected.wall, minWall);
  corrected.bottom = Math.max(corrected.bottom, minWall);
  corrected.lidThickness = Math.max(corrected.lidThickness, minWall);
  corrected.radius = Math.max(0, Math.min(corrected.radius, Math.min(corrected.length, corrected.width) / 2 - corrected.wall - 0.5));
  const minHinge = pinDiameter(corrected.pinType) + effectiveHingeClearance(corrected) * 2 + corrected.nozzle;
  corrected.hingeDiameter = Math.max(corrected.hingeDiameter, minHinge);
  corrected.dividerThickness = Math.max(corrected.dividerThickness, corrected.nozzle * 2);
  return corrected;
}
