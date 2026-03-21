/**
 * AutoSlice — BedPlate
 *
 * Renders a visually distinct build-plate surface inside the 3D viewer.
 * Each BedPlateType has its own color palette, material properties, and
 * a procedural canvas texture where appropriate.
 *
 * Adding a new bed type:
 *   1. Add an entry to BED_PLATE_CONFIGS.
 *   2. Export the literal to BedPlateType.
 *   Done — no other files need to change.
 */

"use client";

import { useMemo } from "react";
import { Html } from "@react-three/drei";
import * as THREE from "three";

// ── Types ─────────────────────────────────────────────────────────────────────

export type BedPlateType =
  | "cold_plate"
  | "textured_pei"
  | "smooth_pei"
  | "high_temp";

export interface BedPlateConfig {
  id:              BedPlateType;
  label:           string;
  /** Hex string used for the plate surface mesh. */
  color:           string;
  roughness:       number;
  metalness:       number;
  /** Primary (brighter) grid line colour. */
  gridPrimary:     string;
  /** Secondary (dimmer) grid cell colour. */
  gridSecondary:   string;
  /** Whether to generate a procedural canvas bump texture. */
  procTexture?:    "noise" | "lines" | "none";
  /** Small accent strip colour along the plate rim. */
  rimColor:        string;
}

// ── Bed plate definitions ─────────────────────────────────────────────────────

export const BED_PLATE_CONFIGS: Record<BedPlateType, BedPlateConfig> = {
  cold_plate: {
    id:            "cold_plate",
    label:         "Cold Plate",
    color:         "#0e1d28",       // deep steel blue
    roughness:     0.88,
    metalness:     0.10,
    gridPrimary:   "#1c3a50",
    gridSecondary: "#0e2030",
    procTexture:   "none",
    rimColor:      "#1e4060",
  },
  textured_pei: {
    id:            "textured_pei",
    label:         "Textured PEI",
    color:         "#18180e",       // warm dark charcoal
    roughness:     1.0,
    metalness:     0.0,
    gridPrimary:   "#2e2e1a",
    gridSecondary: "#1c1c0e",
    procTexture:   "noise",
    rimColor:      "#2e2a14",
  },
  smooth_pei: {
    id:            "smooth_pei",
    label:         "Smooth PEI",
    color:         "#121220",       // cool dark violet-grey
    roughness:     0.22,
    metalness:     0.22,
    gridPrimary:   "#262640",
    gridSecondary: "#141430",
    procTexture:   "none",
    rimColor:      "#2a2a50",
  },
  high_temp: {
    id:            "high_temp",
    label:         "High Temp",
    color:         "#1c1008",       // dark amber-brown
    roughness:     0.80,
    metalness:     0.14,
    gridPrimary:   "#342010",
    gridSecondary: "#201408",
    procTexture:   "lines",
    rimColor:      "#3a2010",
  },
};

// ── Procedural textures ───────────────────────────────────────────────────────

/** Fine random-dot noise → simulates rough PEI surface. */
function makeNoiseTexture(size = 512): THREE.CanvasTexture {
  const canvas  = document.createElement("canvas");
  canvas.width  = size;
  canvas.height = size;
  const ctx     = canvas.getContext("2d")!;

  ctx.fillStyle = "#18180e";
  ctx.fillRect(0, 0, size, size);

  for (let i = 0; i < 10_000; i++) {
    const x    = Math.random() * size;
    const y    = Math.random() * size;
    const r    = Math.random() * 1.4 + 0.2;
    const lum  = Math.floor(Math.random() * 28 + 8);
    ctx.fillStyle = `rgba(${lum + 12},${lum + 10},${lum - 2},${(Math.random() * 0.5 + 0.2).toFixed(2)})`;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
  }

  const tex      = new THREE.CanvasTexture(canvas);
  tex.wrapS      = THREE.RepeatWrapping;
  tex.wrapT      = THREE.RepeatWrapping;
  tex.repeat.set(4, 4);
  return tex;
}

/** Fine horizontal lines → simulates engineered high-temp surface. */
function makeLinesTexture(size = 512): THREE.CanvasTexture {
  const canvas  = document.createElement("canvas");
  canvas.width  = size;
  canvas.height = size;
  const ctx     = canvas.getContext("2d")!;

  ctx.fillStyle = "#1c1008";
  ctx.fillRect(0, 0, size, size);

  const lineEvery = 6;
  ctx.strokeStyle = "rgba(80,48,20,0.35)";
  ctx.lineWidth   = 1;
  for (let y = 0; y < size; y += lineEvery) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(size, y);
    ctx.stroke();
  }

  const tex      = new THREE.CanvasTexture(canvas);
  tex.wrapS      = THREE.RepeatWrapping;
  tex.wrapT      = THREE.RepeatWrapping;
  tex.repeat.set(3, 3);
  return tex;
}

// ── BedPlate component ────────────────────────────────────────────────────────

interface BedPlateProps {
  /** Y position of the plate surface (bottom of the model bounding box). */
  plateY:   number;
  bedType:  BedPlateType;
  /** Width and depth of the plate in mm / scene units. Default 256. */
  size?:    number;
}

export function BedPlate({ plateY, bedType, size = 256 }: BedPlateProps) {
  const cfg = BED_PLATE_CONFIGS[bedType];

  // Build procedural texture once per bed type change
  const mapTexture = useMemo<THREE.CanvasTexture | null>(() => {
    if (typeof document === "undefined") return null;
    if (cfg.procTexture === "noise") return makeNoiseTexture();
    if (cfg.procTexture === "lines") return makeLinesTexture();
    return null;
  }, [cfg.procTexture]);

  // Build surface material once per config change
  const surfaceMat = useMemo(() => {
    const mat = new THREE.MeshStandardMaterial({
      color:     new THREE.Color(cfg.color),
      roughness: cfg.roughness,
      metalness: cfg.metalness,
    });
    if (mapTexture) mat.map = mapTexture;
    return mat;
  }, [cfg.color, cfg.roughness, cfg.metalness, mapTexture]);

  // Dispose old material/texture when they change
  // (React garbage-collects the Three.js objects via useMemo cache invalidation)

  const half = size / 2;

  return (
    <group position={[0, plateY, 0]}>
      {/* Grid lines — updated colours per type */}
      <gridHelper args={[size, 24, cfg.gridPrimary, cfg.gridSecondary]} />

      {/* Main plate surface */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow material={surfaceMat}>
        <planeGeometry args={[size, size]} />
      </mesh>

      {/* Rim — thin coloured border strip around the plate edge */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.4, 0]}>
        <ringGeometry args={[half - 2, half, 64]} />
        <meshStandardMaterial color={cfg.rimColor} roughness={0.55} metalness={0.4} />
      </mesh>

      {/* In-scene label — bottom-left of the plate */}
      <Html
        position={[-half + 4, 1.5, -half + 4]}
        distanceFactor={90}
        style={{ pointerEvents: "none" }}
      >
        <span style={{
          display:      "inline-block",
          padding:      "2px 6px",
          background:   "rgba(0,0,0,0.55)",
          border:       `1px solid ${cfg.rimColor}55`,
          borderRadius: "3px",
          color:        "rgba(255,255,255,0.40)",
          fontSize:     "9px",
          fontFamily:   "monospace",
          letterSpacing: "0.06em",
          whiteSpace:   "nowrap",
          userSelect:   "none",
        }}>
          {cfg.label}
        </span>
      </Html>
    </group>
  );
}
