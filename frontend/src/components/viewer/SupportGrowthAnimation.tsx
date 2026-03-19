"use client";

/**
 * AutoSlice — Support Growth Animation
 *
 * Staged 6-phase animation showing how tree supports are generated.
 * Runs inside an R3F Canvas. All geometry mutations happen through
 * Three.js refs in useFrame — no React re-renders during playback.
 *
 * Phase timeline (normalized 0→1):
 *   Phase 1  [0.00→0.15]  Overhang islands pulse
 *   Phase 2  [0.15→0.28]  Root nodes appear on build plate
 *   Phase 3  [0.28→0.52]  Trunk segments grow upward
 *   Phase 4  [0.52→0.80]  Branch segments split outward
 *   Phase 5  [0.80→0.92]  Tip contacts connect to underside
 *   Phase 6  [0.92→1.00]  Fade into final support mesh
 */

import { useEffect, useRef, useMemo, useCallback } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { TreeSupportResult, TreeNode, TreeSegment, OverhangCluster } from "@/lib/tree-support/types";

// ── Phase thresholds ──────────────────────────────────────────────────────────

const P1_START = 0.00;
const P2_START = 0.15;
const P3_START = 0.28;
const P4_START = 0.52;
const P5_START = 0.80;
const P6_START = 0.92;

const TOTAL_DURATION_S = 7.0;  // seconds at 1× speed
const Y_AXIS = new THREE.Vector3(0, 1, 0);

// ── Segment timeline entry ────────────────────────────────────────────────────

interface SegTimeline {
  segId:       number;
  t0:          number;          // normalized [0,1] reveal start
  t1:          number;          // normalized [0,1] reveal end
  startPos:    THREE.Vector3;
  dir:         THREE.Vector3;   // unit vector startPos→endPos
  len:         number;
  quaternion:  THREE.Quaternion;
  r1:          number;
  r2:          number;
  color:       string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function segColor(startNode: TreeNode): string {
  switch (startNode.type) {
    case "root":    return "#6bb3ff";
    case "trunk":   return "#5a9eef";
    case "branch":  return "#ff9f40";
    case "tip":     return "#ff6030";
    case "contact": return "#ff3333";
    default:        return "#888888";
  }
}

/** BFS depth assignment from root nodes. */
function computeDepths(
  nodes: Map<number, TreeNode>,
): Map<number, number> {
  const depths = new Map<number, number>();
  const queue: number[] = [];

  for (const node of nodes.values()) {
    if (node.parentId === null) {
      depths.set(node.id, 0);
      queue.push(node.id);
    }
  }

  let head = 0;
  while (head < queue.length) {
    const nodeId = queue[head++];
    const node   = nodes.get(nodeId)!;
    const d      = depths.get(nodeId)!;
    for (const childId of node.childIds) {
      if (!depths.has(childId)) {
        depths.set(childId, d + 1);
        queue.push(childId);
      }
    }
  }

  return depths;
}

/** Map node depth → phase bucket. */
function depthToPhaseRange(depth: number, nodeType: string): [number, number] {
  if (nodeType === "root")    return [P2_START, P3_START];
  if (nodeType === "trunk" || depth <= 1) return [P3_START, P4_START];
  if (nodeType === "tip" || nodeType === "contact") return [P5_START, P6_START];
  return [P4_START, P5_START];  // branches
}

/** Build per-segment animation timeline. */
function buildTimeline(
  segments: TreeSegment[],
  nodes:    Map<number, TreeNode>,
): SegTimeline[] {
  const depths = computeDepths(nodes);

  // Group segments by phase bucket
  const buckets = new Map<string, SegTimeline[]>();

  const entries: SegTimeline[] = [];

  for (const seg of segments) {
    const a = nodes.get(seg.startNodeId);
    const b = nodes.get(seg.endNodeId);
    if (!a || !b) continue;

    const dir = b.position.clone().sub(a.position);
    const len = dir.length();
    if (len < 0.5) continue;
    dir.divideScalar(len);

    const q    = new THREE.Quaternion().setFromUnitVectors(Y_AXIS, dir);
    const d    = depths.get(b.id) ?? 0;
    const [pStart, pEnd] = depthToPhaseRange(d, b.type);
    const key  = `${pStart}_${pEnd}`;
    if (!buckets.has(key)) buckets.set(key, []);

    const entry: SegTimeline = {
      segId:      seg.id,
      t0:         pStart,      // will be refined below
      t1:         pEnd,
      startPos:   a.position.clone(),
      dir,
      len,
      quaternion: q,
      r1:         seg.radiusStart,
      r2:         seg.radiusEnd,
      color:      segColor(a),
    };
    buckets.get(key)!.push(entry);
    entries.push(entry);
  }

  // Within each bucket, stagger segments for a cascade effect
  for (const segs of buckets.values()) {
    const n     = segs.length;
    const total = (segs[0].t1 - segs[0].t0);
    const growW = total * 0.30;   // each segment takes 30% of phase to grow
    const spreadW = total * 0.70; // spread reveals across 70% of phase

    segs.forEach((s, i) => {
      const offset = n > 1 ? (i / (n - 1)) * spreadW : spreadW * 0.5;
      s.t0 = s.t0 + offset;
      s.t1 = s.t0 + growW;
    });
  }

  return entries;
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface SupportGrowthAnimationProps {
  result:           TreeSupportResult;
  playing:          boolean;
  progress:         number;          // 0→1, controlled externally
  speed:            number;          // 0.5 | 1 | 2
  onProgressUpdate: (p: number) => void;
  selectedSegmentId:  number | null;
  onSegmentClick:     (segId: number | null) => void;
}

// ── Main component (must run inside R3F Canvas) ───────────────────────────────

export function SupportGrowthAnimation({
  result,
  playing,
  progress,
  speed,
  onProgressUpdate,
  selectedSegmentId,
  onSegmentClick,
}: SupportGrowthAnimationProps) {
  const { nodes, segments, clusters } = result;

  // ── Refs ───────────────────────────────────────────────────────────────────
  const progressRef  = useRef(progress);
  const playingRef   = useRef(playing);
  const speedRef     = useRef(speed);
  const lastEmitRef  = useRef(0);
  const groupRef     = useRef<THREE.Group>(null);

  // Sync external state → refs (no re-render triggered)
  useEffect(() => { progressRef.current  = progress; },  [progress]);
  useEffect(() => { playingRef.current   = playing;  },  [playing]);
  useEffect(() => { speedRef.current     = speed;    },  [speed]);

  // ── Timeline ───────────────────────────────────────────────────────────────
  const timeline = useMemo(() => buildTimeline(segments, nodes), [segments, nodes]);

  // ── Cluster data for Phase 1 ───────────────────────────────────────────────
  const clusterPositions = useMemo(
    () => clusters.map(cl => cl.centroid.clone()),
    [clusters],
  );

  // ── Mesh refs array (one per segment) ────────────────────────────────────
  const meshRefs = useRef<(THREE.Mesh | null)[]>([]);
  // ── Sphere refs for clusters (Phase 1) ────────────────────────────────────
  const clusterRefs = useRef<(THREE.Mesh | null)[]>([]);
  // ── Sphere refs for root nodes (Phase 2) ──────────────────────────────────
  const rootNodeRefs = useRef<(THREE.Mesh | null)[]>([]);

  const rootNodes = useMemo(
    () => [...nodes.values()].filter(n => n.type === "root"),
    [nodes],
  );

  // ── useFrame: drive animation ─────────────────────────────────────────────

  useFrame((_, delta) => {
    // 1. Advance time
    if (playingRef.current) {
      progressRef.current = Math.min(
        progressRef.current + (delta * speedRef.current) / TOTAL_DURATION_S,
        1.0,
      );
      // Throttle callback to ~10fps to avoid too many React re-renders
      const now = performance.now();
      if (now - lastEmitRef.current > 100) {
        lastEmitRef.current = now;
        onProgressUpdate(progressRef.current);
      }
    }

    const t = progressRef.current;

    // 2. Phase 1: cluster sphere opacity pulse
    const p1 = clamp((t - P1_START) / (P2_START - P1_START), 0, 1);
    clusterRefs.current.forEach(mesh => {
      if (!mesh) return;
      const pulse = Math.abs(Math.sin(t * TOTAL_DURATION_S * 3.0));
      const mat   = mesh.material as THREE.MeshStandardMaterial;
      mesh.visible = p1 > 0.01;
      mat.opacity  = clamp(p1 * pulse * 0.9 + 0.1, 0, 1);
      const s = 1.0 + pulse * 0.3;
      mesh.scale.setScalar(clamp(p1 * s, 0, 1.5));
    });

    // 3. Phase 2: root spheres scale up
    const p2 = clamp((t - P2_START) / (P3_START - P2_START), 0, 1);
    rootNodeRefs.current.forEach((mesh, i) => {
      if (!mesh) return;
      const stagger = rootNodes.length > 1 ? i / (rootNodes.length - 1) * 0.7 : 0;
      const f = clamp((p2 - stagger) / 0.3, 0, 1);
      mesh.visible = f > 0;
      mesh.scale.setScalar(f);
    });

    // 4. Segments: Phase 3-5 cascade growth
    timeline.forEach((seg, i) => {
      const mesh = meshRefs.current[i];
      if (!mesh) return;

      const f = clamp((t - seg.t0) / Math.max(seg.t1 - seg.t0, 0.01), 0, 1);

      if (f <= 0) {
        mesh.visible = false;
        return;
      }

      mesh.visible  = true;
      mesh.scale.y  = f;

      // Grow from startPos toward endPos
      const growLen = seg.len * f;
      mesh.position.copy(seg.startPos).addScaledVector(seg.dir, growLen * 0.5);

      // Phase 6 fade (animation ending)
      const p6 = clamp((t - P6_START) / (1.0 - P6_START), 0, 1);
      const mat = mesh.material as THREE.MeshStandardMaterial;
      if (mat.transparent) mat.opacity = 1.0 - p6;
    });
  });

  // ── Click handler ─────────────────────────────────────────────────────────
  const handleClick = useCallback((segId: number) => {
    onSegmentClick(selectedSegmentId === segId ? null : segId);
  }, [selectedSegmentId, onSegmentClick]);

  const radialSegs = 8;

  return (
    <group ref={groupRef} name="support-growth-animation">

      {/* Phase 1 — Cluster highlight spheres */}
      {clusterPositions.map((pos, i) => (
        <mesh
          key={`cluster-${i}`}
          ref={el => { clusterRefs.current[i] = el; }}
          position={pos.toArray() as [number, number, number]}
          visible={false}
        >
          <sphereGeometry args={[Math.max((clusters[i] as OverhangCluster).area * 0.012 + 1.5, 2), 10, 7]} />
          <meshStandardMaterial
            color="#ff4400"
            transparent
            opacity={0}
            depthWrite={false}
            emissive="#ff2200"
            emissiveIntensity={0.5}
          />
        </mesh>
      ))}

      {/* Phase 2 — Root node spheres */}
      {rootNodes.map((node, i) => (
        <mesh
          key={`root-${node.id}`}
          ref={el => { rootNodeRefs.current[i] = el; }}
          position={node.position.toArray() as [number, number, number]}
          scale={0}
          visible={false}
        >
          <sphereGeometry args={[node.radius * 1.4, 10, 7]} />
          <meshStandardMaterial color="#4a9eff" roughness={0.5} />
        </mesh>
      ))}

      {/* Phases 3-5 — Growing segment cylinders */}
      {timeline.map((seg, i) => {
        const isSelected = selectedSegmentId !== null &&
          segments[i]?.id === selectedSegmentId;
        return (
          <mesh
            key={`seg-${seg.segId}`}
            ref={el => { meshRefs.current[i] = el; }}
            quaternion={seg.quaternion}
            visible={false}
            onClick={(e) => { e.stopPropagation(); handleClick(seg.segId); }}
          >
            <cylinderGeometry args={[seg.r2, seg.r1, seg.len, radialSegs, 1]} />
            <meshStandardMaterial
              color={isSelected ? "#ffffff" : seg.color}
              roughness={0.5}
              metalness={0.05}
              transparent
              opacity={1}
              emissive={isSelected ? "#ffffff" : "#000000"}
              emissiveIntensity={isSelected ? 0.4 : 0}
            />
          </mesh>
        );
      })}
    </group>
  );
}

// ── Phase label helper (used by sidebar) ─────────────────────────────────────

export function getAnimPhaseLabel(progress: number): { phase: number; label: string; desc: string } {
  if (progress < P2_START)  return { phase: 1, label: "Phase 1", desc: "Detecting overhang islands" };
  if (progress < P3_START)  return { phase: 2, label: "Phase 2", desc: "Placing support roots" };
  if (progress < P4_START)  return { phase: 3, label: "Phase 3", desc: "Growing trunk columns" };
  if (progress < P5_START)  return { phase: 4, label: "Phase 4", desc: "Branching toward overhangs" };
  if (progress < P6_START)  return { phase: 5, label: "Phase 5", desc: "Connecting tip contacts" };
  return                           { phase: 6, label: "Phase 6", desc: "Finalizing support mesh" };
}
