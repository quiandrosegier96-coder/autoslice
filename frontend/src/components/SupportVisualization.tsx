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

type SupportDebugLayers = {
  /** All detected overhang triangles before self-support / floor filtering */
  all_overhang_positions:    number[];
  /** Cluster centroids that received a column */
  active_candidate_points:   number[];
  /** Cluster centroids that were filtered out (self-supported, too short, floor) */
  filtered_candidate_points: number[];
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
  debug:              SupportDebugLayers | null;
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

/** Orange mesh — overhang faces that need support */
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

/** Blue mesh — all detected overhang faces (debug layer, before filtering) */
function AllOverhangMesh({ positions }: { positions: Float32Array }) {
  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.computeVertexNormals();
    return geo;
  }, [positions]);

  return (
    <mesh geometry={geometry} renderOrder={1}>
      <meshStandardMaterial
        color="#3388ff"
        transparent
        opacity={0.30}
        side={THREE.DoubleSide}
        depthWrite={false}
      />
    </mesh>
  );
}

/** Support column — positioned at the correct z_bottom (not always build plate) */
function Column({
  col, cx, cy, cz,
}: {
  col: SupportColumn;
  cx: number; cy: number; cz: number;
}) {
  const height = Math.max(col.z_top - col.z_bottom, 0.5);
  const halfH  = height / 2;
  // Column centre is midpoint in 3MF Z between z_bottom and z_top
  const colCenterZ          = col.z_bottom + halfH;
  const [px, py, pz]        = toThreePos(col.x, col.y, colCenterZ, cx, cy, cz);

  return (
    <mesh position={[px, py, pz]} renderOrder={1}>
      <cylinderGeometry args={[col.radius, col.radius * 1.1, height, 8, 1]} />
      <meshStandardMaterial
        color="#aaaaaa"
        transparent
        opacity={0.35}
        depthWrite={false}
      />
    </mesh>
  );
}

/** Small sphere — debug candidate point */
function CandidatePoint({
  x, y, z,
  cx, cy, cz,
  active,
}: {
  x: number; y: number; z: number;
  cx: number; cy: number; cz: number;
  active: boolean;
}) {
  const [px, py, pz] = toThreePos(x, y, z, cx, cy, cz);
  return (
    <mesh position={[px, py, pz]} renderOrder={3}>
      <sphereGeometry args={[0.8, 6, 6]} />
      <meshStandardMaterial
        color={active ? "#22dd77" : "#dd2222"}
        transparent
        opacity={0.85}
      />
    </mesh>
  );
}

// ── Debug layer renderer ──────────────────────────────────────────────────────

type DebugLayers = {
  showAllOverhangs: boolean;
  showActiveCandidates: boolean;
  showFilteredCandidates: boolean;
};

function DebugVisualization({
  data, cx, cy, cz, layers,
}: {
  data: SupportDebugLayers;
  cx: number; cy: number; cz: number;
  layers: DebugLayers;
}) {
  const allOvPositions = useMemo(
    () => transformBuffer(data.all_overhang_positions, cx, cy, cz),
    [data.all_overhang_positions, cx, cy, cz],
  );

  const activePoints = useMemo(() => {
    const pts: [number, number, number][] = [];
    for (let i = 0; i < data.active_candidate_points.length; i += 3) {
      pts.push([
        data.active_candidate_points[i],
        data.active_candidate_points[i + 1],
        data.active_candidate_points[i + 2],
      ]);
    }
    return pts;
  }, [data.active_candidate_points]);

  const filteredPoints = useMemo(() => {
    const pts: [number, number, number][] = [];
    for (let i = 0; i < data.filtered_candidate_points.length; i += 3) {
      pts.push([
        data.filtered_candidate_points[i],
        data.filtered_candidate_points[i + 1],
        data.filtered_candidate_points[i + 2],
      ]);
    }
    return pts;
  }, [data.filtered_candidate_points]);

  return (
    <group>
      {layers.showAllOverhangs && allOvPositions.length > 0 && (
        <AllOverhangMesh positions={allOvPositions} />
      )}
      {layers.showActiveCandidates && activePoints.map(([x, y, z], i) => (
        <CandidatePoint key={`a${i}`} x={x} y={y} z={z} cx={cx} cy={cy} cz={cz} active />
      ))}
      {layers.showFilteredCandidates && filteredPoints.map(([x, y, z], i) => (
        <CandidatePoint key={`f${i}`} x={x} y={y} z={z} cx={cx} cy={cy} cz={cz} active={false} />
      ))}
    </group>
  );
}

// ── Props ─────────────────────────────────────────────────────────────────────

export type SupportDebugLayerToggles = {
  showAllOverhangs:       boolean;
  showActiveCandidates:   boolean;
  showFilteredCandidates: boolean;
};

interface SupportVisualizationProps {
  jobId:       string;
  /** Pass true to fetch ?debug=true and make debug layer data available */
  debugMode?:  boolean;
  /** When debugMode=true, controls which debug layers are visible */
  debugLayers?: SupportDebugLayerToggles;
}

// ── Main component ────────────────────────────────────────────────────────────

export function SupportVisualization({
  jobId,
  debugMode  = false,
  debugLayers = {
    showAllOverhangs:       false,
    showActiveCandidates:   false,
    showFilteredCandidates: false,
  },
}: SupportVisualizationProps) {
  const [data,    setData]    = useState<SupportPreviewData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const url = `/api/analyze/${jobId}/support-preview${debugMode ? "?debug=true" : ""}`;
    fetch(url)
      .then((r) => r.json())
      .then((d: SupportPreviewData) => {
        if (!cancelled) { setData(d); setLoading(false); }
      })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [jobId, debugMode]);

  if (loading || !data || !data.needs_supports) return null;

  const [cx, cy, cz] = data.model_center;
  const positions    = transformBuffer(data.overhang_positions, cx, cy, cz);

  const anyDebugLayer = debugMode && data.debug && (
    debugLayers.showAllOverhangs ||
    debugLayers.showActiveCandidates ||
    debugLayers.showFilteredCandidates
  );

  return (
    <group>
      {positions.length > 0 && <OverhangMesh positions={positions} />}
      {data.support_columns.map((col, i) => (
        <Column key={i} col={col} cx={cx} cy={cy} cz={cz} />
      ))}
      {anyDebugLayer && data.debug && (
        <DebugVisualization
          data={data.debug}
          cx={cx} cy={cy} cz={cz}
          layers={debugLayers}
        />
      )}
    </group>
  );
}
