"use client";

import { useEffect, useMemo, useState } from "react";
import * as THREE from "three";

// ── Types ─────────────────────────────────────────────────────────────────────

type SupportColumn = {
  x:        number;
  y:        number;
  z_bottom: number;
  z_top:    number;
  radius:   number;
};

type SupportPreviewData = {
  job_id:             string;
  needs_supports:     boolean;
  support_type:       string;
  placement:          string;
  overhang_positions: number[];
  overhang_severity:  string[];
  support_columns:    SupportColumn[];
  model_center:       [number, number, number];
  overhang_area_mm2:  number;
  column_count:       number;
};

// ── Coordinate transform ──────────────────────────────────────────────────────
//
// ThreeMFLoader applies rotation.x = -π/2 to the loaded group, converting
// 3MF's Z-up space to Three.js Y-up. AutoCamera then subtracts the bounding-
// box center so the model appears at scene origin.
//
// For support geometry to align we apply the same two transforms:
//   1. -π/2 X rotation:  (x, y, z) → (x, z, -y)
//   2. subtract center:  (x-cx, z-cz, -y-(-cy)) = (x-cx, z-cz, cy-y)
//
// where (cx, cy, cz) is the model bounding-box center in 3MF space.

function transformBuffer(
  raw: number[],
  cx: number, cy: number, cz: number,
): Float32Array {
  const out = new Float32Array(raw.length);
  for (let i = 0; i < raw.length; i += 3) {
    out[i]     = raw[i]     - cx;   // x - cx
    out[i + 1] = raw[i + 2] - cz;  // z - cz  (Three.js Y = 3MF Z)
    out[i + 2] = cy - raw[i + 1];  // cy - y  (Three.js Z = -(3MF Y))
  }
  return out;
}

function toThreePos(
  x: number, y: number, z: number,
  cx: number, cy: number, cz: number,
): [number, number, number] {
  return [x - cx, z - cz, cy - y];
}

// ── Sub-components ────────────────────────────────────────────────────────────

function OverhangMesh({ positions }: { positions: Float32Array }) {
  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.computeVertexNormals();
    return geo;
  }, [positions]);

  return (
    <mesh geometry={geometry} renderOrder={2}>
      <meshStandardMaterial
        color="#ff5500"
        transparent
        opacity={0.70}
        side={THREE.DoubleSide}
        depthWrite={false}
      />
    </mesh>
  );
}

function Column({
  col, cx, cy, cz,
}: {
  col: SupportColumn;
  cx: number; cy: number; cz: number;
}) {
  const height   = Math.max(col.z_top - col.z_bottom, 0.5);
  const halfH    = height / 2;
  // Column center is midpoint between z_bottom and z_top
  const colCenterZ = col.z_bottom + halfH;
  const [px, py, pz] = toThreePos(col.x, col.y, colCenterZ, cx, cy, cz);

  return (
    <mesh position={[px, py, pz]} renderOrder={1}>
      <cylinderGeometry args={[col.radius, col.radius * 1.1, height, 8, 1]} />
      <meshStandardMaterial
        color="#aaaaaa"
        transparent
        opacity={0.30}
        depthWrite={false}
      />
    </mesh>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function SupportVisualization({ jobId }: { jobId: string }) {
  const [data, setData]       = useState<SupportPreviewData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`/api/analyze/${jobId}/support-preview`)
      .then((r) => r.json())
      .then((d: SupportPreviewData) => { if (!cancelled) { setData(d); setLoading(false); } })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [jobId]);

  if (loading || !data || !data.needs_supports) return null;

  const [cx, cy, cz] = data.model_center;
  const positions = transformBuffer(data.overhang_positions, cx, cy, cz);

  return (
    <group>
      {positions.length > 0 && <OverhangMesh positions={positions} />}
      {data.support_columns.map((col, i) => (
        <Column key={i} col={col} cx={cx} cy={cy} cz={cz} />
      ))}
    </group>
  );
}
