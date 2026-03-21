/**
 * AutoSlice — Support Debug Face Overlay
 *
 * Renders four semi-transparent face layers on top of the model:
 *
 *   Red    (#ef4444, 0.55) — allOverhangs:  every downward-facing face detected
 *   Orange (#f97316, 0.70) — needsSupport:  faces that pass the raycast filter
 *   Yellow (#facc15, 1.00) — cluster tips:  contact-point spheres per cluster
 *   Green  (#22c55e, 1.00) — support nodes: root / trunk / branch / tip spheres
 *
 * Yellow and green are always shown when this overlay is active.
 * Red / orange are only rendered when debugFaces is present (showDebug=true).
 *
 * Usage (inside a @react-three/fiber Canvas):
 *   <DebugFaceOverlay result={treeResult} />
 */

"use client";

import { useMemo } from "react";
import * as THREE from "three";
import type { OverhangFace, TreeSupportResult } from "@/lib/tree-support/types";

// ── Face geometry builder ──────────────────────────────────────────────────────

/**
 * Build a BufferGeometry with vertex colours from an array of OverhangFaces.
 * Each triangle is flat-shaded with the supplied colour.
 */
function buildFaceGeometry(
  faces: OverhangFace[],
  r: number, g: number, b: number,
): THREE.BufferGeometry {
  const positions = new Float32Array(faces.length * 9);   // 3 verts × 3 xyz
  const colors    = new Float32Array(faces.length * 9);   // 3 verts × 3 rgb

  for (let i = 0; i < faces.length; i++) {
    const [v0, v1, v2] = faces[i].vertices;
    const o = i * 9;
    positions[o]     = v0.x; positions[o + 1] = v0.y; positions[o + 2] = v0.z;
    positions[o + 3] = v1.x; positions[o + 4] = v1.y; positions[o + 5] = v1.z;
    positions[o + 6] = v2.x; positions[o + 7] = v2.y; positions[o + 8] = v2.z;
    for (let v = 0; v < 3; v++) {
      colors[o + v * 3]     = r;
      colors[o + v * 3 + 1] = g;
      colors[o + v * 3 + 2] = b;
    }
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geo.setAttribute("color",    new THREE.BufferAttribute(colors,    3));
  return geo;
}

// ── Shared materials ───────────────────────────────────────────────────────────

function makeMat(opacity: number) {
  return new THREE.MeshBasicMaterial({
    vertexColors: true,
    transparent:  true,
    opacity,
    depthWrite:   false,
    side:         THREE.DoubleSide,
    polygonOffset: true,
    polygonOffsetFactor: -2,
    polygonOffsetUnits:  -2,
  });
}

const MAT_RED    = makeMat(0.45);   // all overhangs
const MAT_ORANGE = makeMat(0.65);   // needs-support faces
const MAT_YELLOW = new THREE.MeshBasicMaterial({ color: 0xfacc15, depthWrite: false });
const MAT_GREEN  = new THREE.MeshBasicMaterial({ color: 0x22c55e, depthWrite: false });

// ── Component ─────────────────────────────────────────────────────────────────

interface DebugFaceOverlayProps {
  result: TreeSupportResult;
}

export function DebugFaceOverlay({ result }: DebugFaceOverlayProps) {
  const { debugFaces, clusters, nodes } = result;

  // ── Red: all overhang faces ──────────────────────────────────────────────
  const redGeo = useMemo(() => {
    if (!debugFaces?.allOverhangs.length) return null;
    return buildFaceGeometry(debugFaces.allOverhangs, 0.937, 0.267, 0.267);
  }, [debugFaces]);

  // ── Orange: faces that actually need support ──────────────────────────────
  const orangeGeo = useMemo(() => {
    if (!debugFaces?.needsSupport.length) return null;
    return buildFaceGeometry(debugFaces.needsSupport, 0.976, 0.451, 0.086);
  }, [debugFaces]);

  // ── Yellow: cluster tip/contact positions ────────────────────────────────
  const yellowPositions = useMemo(
    () => clusters.map((c) => c.tipPosition),
    [clusters],
  );

  // ── Green: all support nodes ─────────────────────────────────────────────
  const greenPositions = useMemo(
    () => Array.from(nodes.values()).map((n) => n.position),
    [nodes],
  );

  return (
    <group name="debug-face-overlay">
      {/* Red — all detected overhang faces */}
      {redGeo && (
        <mesh geometry={redGeo} material={MAT_RED} renderOrder={1} />
      )}

      {/* Orange — faces that passed the raycast filter (true support needs) */}
      {orangeGeo && (
        <mesh geometry={orangeGeo} material={MAT_ORANGE} renderOrder={2} />
      )}

      {/* Yellow — cluster contact points */}
      {yellowPositions.map((pos, i) => (
        <mesh key={`tip-${i}`} position={pos} material={MAT_YELLOW} renderOrder={3}>
          <sphereGeometry args={[0.8, 6, 4]} />
        </mesh>
      ))}

      {/* Green — every node in the support graph */}
      {greenPositions.map((pos, i) => (
        <mesh key={`node-${i}`} position={pos} material={MAT_GREEN} renderOrder={4}>
          <sphereGeometry args={[0.5, 5, 3]} />
        </mesh>
      ))}
    </group>
  );
}

// ── Legend data (consumed by sidebar) ─────────────────────────────────────────

export const DEBUG_FACE_LEGEND = [
  { color: "#ef4444", label: "All overhangs",        desc: "Every downward-facing face (>45°)" },
  { color: "#f97316", label: "Needs support",        desc: "Passes downward raycast — no geometry below" },
  { color: "#facc15", label: "Contact points",       desc: "Cluster tip positions" },
  { color: "#22c55e", label: "Support graph nodes",  desc: "Root / trunk / branch / tip" },
] as const;
