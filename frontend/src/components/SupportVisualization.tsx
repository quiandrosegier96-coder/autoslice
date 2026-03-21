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

type TreeBranch = {
  id:           number;
  parent_id:    number | null;
  start_x:      number;
  start_y:      number;
  start_z:      number;
  end_x:        number;
  end_y:        number;
  end_z:        number;
  start_radius: number;
  end_radius:   number;
  is_tip:       boolean;
};

type SupportDebugLayers = {
  all_overhang_positions:    number[];
  active_candidate_points:   number[];
  filtered_candidate_points: number[];
};

type SupportPreviewData = {
  job_id:             string;
  needs_supports:     boolean;
  support_type:       string;   // "none" | "normal" | "tree"
  placement:          string;
  overhang_positions: number[];
  overhang_severity:  string[];
  support_columns:    SupportColumn[];
  tree_branches:      TreeBranch[];
  trunk_count:        number;
  tip_count:          number;
  model_center:       [number, number, number];
  /** 3MF Z floor — used for the Three.js Y offset after the bottom-align fix. */
  model_floor_z:      number;
  overhang_area_mm2:  number;
  column_count:       number;
  debug:              SupportDebugLayers | null;
};

// ── Coordinate transform ──────────────────────────────────────────────────────
//
// ThreeMFLoader applies rotation.x = -π/2 to the loaded group, converting
// 3MF's Z-up space to Three.js Y-up.  AutoCamera then subtracts the bounding-
// box center so the model appears at scene origin.
//
// For support geometry to align we apply the same two transforms:
//   1. -π/2 X rotation:  (x, y, z) → (x, z, -y)
//   2. subtract center:  (x-cx, z-cz, cy-y)
//
// where (cx, cy, cz) is the model bounding-box center in 3MF space.

function transformBuffer(
  raw: number[],
  cx: number, cy: number, floorZ: number,
): Float32Array {
  const out = new Float32Array(raw.length);
  for (let i = 0; i < raw.length; i += 3) {
    out[i]     = raw[i]     - cx;
    out[i + 1] = raw[i + 2] - floorZ;
    out[i + 2] = cy - raw[i + 1];
  }
  return out;
}

function toThreePos(
  x: number, y: number, z: number,
  cx: number, cy: number, floorZ: number,
): [number, number, number] {
  return [x - cx, z - floorZ, cy - y];
}

// ── Shared Y-axis constant ────────────────────────────────────────────────────

const _UP = new THREE.Vector3(0, 1, 0);

// ── Sub-components ────────────────────────────────────────────────────────────

/** Orange overhang mesh */
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

/** Blue debug mesh — all overhangs before filtering */
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

/** Legacy straight cylinder (used for normal/non-tree support type) */
function Column({ col, cx, cy, floorZ }: { col: SupportColumn; cx: number; cy: number; floorZ: number }) {
  const height = Math.max(col.z_top - col.z_bottom, 0.5);
  const colCenterZ = col.z_bottom + height / 2;
  const [px, py, pz] = toThreePos(col.x, col.y, colCenterZ, cx, cy, floorZ);
  return (
    <mesh position={[px, py, pz]} renderOrder={1}>
      <cylinderGeometry args={[col.radius, col.radius * 1.1, height, 8, 1]} />
      <meshStandardMaterial color="#aaaaaa" transparent opacity={0.35} depthWrite={false} />
    </mesh>
  );
}

// ── Tree support branch segment ───────────────────────────────────────────────

// Material constants — deliberately bold so tree supports are unmistakable
const MAT_TRUNK  = { color: "#C8843A", roughness: 0.75, metalness: 0.05 };  // warm amber-brown trunk
const MAT_BRANCH = { color: "#D4A055", roughness: 0.72, metalness: 0.04 };  // lighter branch
const MAT_TIP    = { color: "#FF6600", roughness: 0.40, metalness: 0.10 };  // bright orange contact

/**
 * Renders one tapered cylinder between two 3D points plus a smoothing sphere
 * at the start joint.  A bright orange contact sphere marks the tip.
 * Fully opaque so tree supports are clearly visible through the model.
 */
function TreeBranchSegment({
  branch, cx, cy, floorZ,
}: {
  branch: TreeBranch;
  cx: number; cy: number; floorZ: number;
}) {
  const [sx, sy, sz] = toThreePos(branch.start_x, branch.start_y, branch.start_z, cx, cy, floorZ);
  const [ex, ey, ez] = toThreePos(branch.end_x,   branch.end_y,   branch.end_z,   cx, cy, floorZ);

  const start = new THREE.Vector3(sx, sy, sz);
  const end   = new THREE.Vector3(ex, ey, ez);
  const dir   = end.clone().sub(start);
  const len   = dir.length();

  if (len < 0.2) return null;

  const mid   = start.clone().lerp(end, 0.5);
  const euler = new THREE.Euler().setFromQuaternion(
    new THREE.Quaternion().setFromUnitVectors(_UP, dir.normalize()),
  );

  const isRoot = branch.parent_id === null;
  const mat    = isRoot ? MAT_TRUNK : MAT_BRANCH;

  return (
    <group>
      {/* Tapered cylinder — fully opaque, depthWrite=true */}
      <mesh
        position={mid.toArray() as [number, number, number]}
        rotation={[euler.x, euler.y, euler.z]}
        renderOrder={1}
      >
        <cylinderGeometry args={[branch.end_radius, branch.start_radius, len, 10, 1]} />
        <meshStandardMaterial
          color={mat.color}
          roughness={mat.roughness}
          metalness={mat.metalness}
        />
      </mesh>

      {/* Smoothing sphere at joint — seals the gap between segments */}
      <mesh position={[sx, sy, sz]} renderOrder={1}>
        <sphereGeometry args={[branch.start_radius, 10, 10]} />
        <meshStandardMaterial color={mat.color} roughness={mat.roughness} metalness={mat.metalness} />
      </mesh>

      {/* Bright contact sphere at tip — marks where the support touches the model */}
      {branch.is_tip && (
        <mesh position={[ex, ey, ez]} renderOrder={3}>
          <sphereGeometry args={[Math.max(branch.end_radius * 2.2, 0.8), 10, 10]} />
          <meshStandardMaterial
            color={MAT_TIP.color}
            roughness={MAT_TIP.roughness}
            metalness={MAT_TIP.metalness}
            emissive="#FF3300"
            emissiveIntensity={0.25}
          />
        </mesh>
      )}
    </group>
  );
}

// ── Debug candidates ──────────────────────────────────────────────────────────

function CandidatePoint({
  x, y, z, cx, cy, floorZ, active,
}: {
  x: number; y: number; z: number;
  cx: number; cy: number; floorZ: number;
  active: boolean;
}) {
  const [px, py, pz] = toThreePos(x, y, z, cx, cy, floorZ);
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

export type SupportDebugLayerToggles = {
  showAllOverhangs:       boolean;
  showActiveCandidates:   boolean;
  showFilteredCandidates: boolean;
};

function DebugVisualization({
  data, cx, cy, floorZ, layers,
}: {
  data: SupportDebugLayers;
  cx: number; cy: number; floorZ: number;
  layers: SupportDebugLayerToggles;
}) {
  const allOvPositions = useMemo(
    () => transformBuffer(data.all_overhang_positions, cx, cy, floorZ),
    [data.all_overhang_positions, cx, cy, floorZ],
  );

  const activePoints = useMemo(() => {
    const pts: [number, number, number][] = [];
    for (let i = 0; i < data.active_candidate_points.length; i += 3) {
      pts.push([data.active_candidate_points[i], data.active_candidate_points[i + 1], data.active_candidate_points[i + 2]]);
    }
    return pts;
  }, [data.active_candidate_points]);

  const filteredPoints = useMemo(() => {
    const pts: [number, number, number][] = [];
    for (let i = 0; i < data.filtered_candidate_points.length; i += 3) {
      pts.push([data.filtered_candidate_points[i], data.filtered_candidate_points[i + 1], data.filtered_candidate_points[i + 2]]);
    }
    return pts;
  }, [data.filtered_candidate_points]);

  return (
    <group>
      {layers.showAllOverhangs && allOvPositions.length > 0 && (
        <AllOverhangMesh positions={allOvPositions} />
      )}
      {layers.showActiveCandidates && activePoints.map(([x, y, z], i) => (
        <CandidatePoint key={`a${i}`} x={x} y={y} z={z} cx={cx} cy={cy} floorZ={floorZ} active />
      ))}
      {layers.showFilteredCandidates && filteredPoints.map(([x, y, z], i) => (
        <CandidatePoint key={`f${i}`} x={x} y={y} z={z} cx={cx} cy={cy} floorZ={floorZ} active={false} />
      ))}
    </group>
  );
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface SupportVisualizationProps {
  jobId:        string;
  debugMode?:   boolean;
  debugLayers?: SupportDebugLayerToggles;
  /** When true only the overhang heatmap is rendered, branches are hidden */
  heatmapOnly?: boolean;
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
  heatmapOnly = false,
}: SupportVisualizationProps) {
  const [data,    setData]    = useState<SupportPreviewData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const url = `/api/analyze/${jobId}/support-preview${debugMode ? "?debug=true" : ""}`;
    fetch(url)
      .then(r => r.json())
      .then((d: SupportPreviewData) => { if (!cancelled) { setData(d); setLoading(false); } })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [jobId, debugMode]);

  if (loading || !data || !data.needs_supports) return null;

  const [cx, cy]  = data.model_center;
  const floorZ    = data.model_floor_z;
  const positions = transformBuffer(data.overhang_positions, cx, cy, floorZ);

  const anyDebugLayer = debugMode && data.debug && (
    debugLayers.showAllOverhangs ||
    debugLayers.showActiveCandidates ||
    debugLayers.showFilteredCandidates
  );

  return (
    <group>
      {/* Overhang heatmap — always shown */}
      {positions.length > 0 && <OverhangMesh positions={positions} />}

      {/* Support geometry — hidden in heatmap-only mode */}
      {!heatmapOnly && (
        <>
          {(data.tree_branches?.length ?? 0) > 0 ? (
            // ── Tree branches (organic, tapered, branching) ──────────────────
            // Used whenever tree_branches are available — regardless of support_type
            data.tree_branches.map(branch => (
              <TreeBranchSegment
                key={branch.id}
                branch={branch}
                cx={cx} cy={cy} floorZ={floorZ}
              />
            ))
          ) : (
            // ── Fallback: straight cylinders (only if no tree data) ───────────
            data.support_columns.map((col, i) => (
              <Column key={i} col={col} cx={cx} cy={cy} floorZ={floorZ} />
            ))
          )}
        </>
      )}

      {anyDebugLayer && data.debug && (
        <DebugVisualization
          data={data.debug}
          cx={cx} cy={cy} floorZ={floorZ}
          layers={debugLayers}
        />
      )}
    </group>
  );
}
