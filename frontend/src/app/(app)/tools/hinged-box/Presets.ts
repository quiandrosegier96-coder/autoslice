export type HingeMode = "none" | "two" | "three" | "continuous";
export type PinType = "filament175" | "metal2" | "metal3" | "printed";
export type LatchType = "none" | "snap" | "magnet" | "lip" | "slide" | "doubleSnap";
export type DividerMode = "none" | "horizontal" | "vertical" | "grid";
export type LidStyle = "flat" | "inset" | "overhang" | "lip";

export type BoxSettings = {
  length: number;
  width: number;
  height: number;
  wall: number;
  bottom: number;
  lidThickness: number;
  radius: number;
  tolerance: number;
  nozzle: number;
  hingeMode: HingeMode;
  hingeDiameter: number;
  pinType: PinType;
  hingeClearanceAuto: boolean;
  hingeClearance: number;
  latchType: LatchType;
  magnetDiameter: number;
  magnetHeight: number;
  magnetCount: number;
  dividerMode: DividerMode;
  dividerRows: number;
  dividerColumns: number;
  dividerThickness: number;
  lidStyle: LidStyle;
  lidLipHeight: number;
  ribs: boolean;
  feet: boolean;
  ventilation: boolean;
  labelHolder: boolean;
  handleCutouts: boolean;
  stackable: boolean;
  cablePass: boolean;
  textTop: string;
  textBottom: string;
  textRaised: boolean;
  textSize: number;
  textDepth: number;
};

export const DEFAULT_SETTINGS: BoxSettings = {
  length: 120,
  width: 80,
  height: 36,
  wall: 1.6,
  bottom: 1.6,
  lidThickness: 2,
  radius: 6,
  tolerance: 0.25,
  nozzle: 0.4,
  hingeMode: "three",
  hingeDiameter: 5,
  pinType: "filament175",
  hingeClearanceAuto: true,
  hingeClearance: 0.25,
  latchType: "snap",
  magnetDiameter: 6,
  magnetHeight: 2,
  magnetCount: 2,
  dividerMode: "none",
  dividerRows: 2,
  dividerColumns: 3,
  dividerThickness: 1.2,
  lidStyle: "lip",
  lidLipHeight: 4,
  ribs: true,
  feet: true,
  ventilation: false,
  labelHolder: false,
  handleCutouts: false,
  stackable: false,
  cablePass: false,
  textTop: "AutoSlice",
  textBottom: "",
  textRaised: true,
  textSize: 10,
  textDepth: 0.8,
};

export const PRESETS: Record<string, Partial<BoxSettings>> = {
  "Mini Box": { length: 70, width: 45, height: 24, hingeMode: "two", latchType: "snap" },
  "Storage Box": { length: 160, width: 110, height: 55, hingeMode: "three", latchType: "doubleSnap", dividerMode: "grid" },
  "Electronics Box": { length: 120, width: 80, height: 34, hingeMode: "three", latchType: "snap", ventilation: true, cablePass: true },
  "Arduino Box": { length: 95, width: 65, height: 28, hingeMode: "two", latchType: "snap", ventilation: true },
  "ESP32 Box": { length: 75, width: 48, height: 24, hingeMode: "two", latchType: "snap", cablePass: true },
  "Raspberry Pi Box": { length: 100, width: 72, height: 30, hingeMode: "three", ventilation: true, cablePass: true },
  "Screw Organizer": { length: 180, width: 120, height: 35, dividerMode: "grid", dividerRows: 3, dividerColumns: 5, latchType: "slide" },
  "Jewelry Box": { length: 110, width: 85, height: 40, radius: 12, latchType: "magnet", magnetCount: 2 },
  "Card Box": { length: 100, width: 72, height: 38, radius: 4, latchType: "lip", hingeMode: "two" },
  "Gaming Box": { length: 150, width: 95, height: 45, radius: 8, dividerMode: "vertical", dividerColumns: 4 },
  "Battery Box": { length: 135, width: 70, height: 32, dividerMode: "vertical", dividerColumns: 6, latchType: "snap" },
};

export const TOLERANCES = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5];
export const WALL_PRESETS = [0.8, 1.2, 1.6, 2, 3];
export const NOZZLES = [0.2, 0.4, 0.6, 0.8];

export function pinDiameter(pinType: PinType) {
  if (pinType === "filament175") return 1.75;
  if (pinType === "metal2") return 2;
  if (pinType === "metal3") return 3;
  return 2.4;
}

export function effectiveHingeClearance(settings: BoxSettings) {
  if (!settings.hingeClearanceAuto) return settings.hingeClearance;
  return Math.max(settings.tolerance, settings.nozzle * 0.45);
}
