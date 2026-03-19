"use client";

/**
 * AutoSlice — Debug Graph Overlay
 *
 * Renders the tree support graph skeleton as debug helpers inside the R3F Canvas:
 *   - Nodes as coloured spheres (type-coded)
 *   - Segments as thin wire lines
 *   - Contact points as bright rings
 *   - Selected highlight
 */

import { useMemo, useRef } from "react";
import * as THREE from "three";
import type { TreeSupportResult } from "@/lib/tree-support/types";

// ── Node colours by type ──────────────────────────────────────────────────────

const NODE_COLORS: Record<string, string> = {
  root:     "#60a5fa",  // blue
  trunk:    "#34d399",  // emerald
  branch:   "#fbbf24",  // amber
  tip:      "#f97316",  // orange
  contact:  "#ef4444",  // red
  waypoint: "#94a3b8",  // slate
};

const NODE_RADII: Record<string, number> = {
  root:     0.9,
  trunk:    0.7,
  branch:   0.55,
  tip:      0.5,
  contact:  0.65,
  waypoint: 0.4,
};

// ── Segment lines using BufferGeometry ────────────────────────────────────────

function SegmentLines({
  result,
  selectedSegmentId,
  onSegmentClick,
}: {
  result: TreeSupportResult;
  selectedSegmentId: number | null;
  onSegmentClick: (id: number | null) => void;
}) {
  const { nodes, segments } = result;

  // Build one LineSegments geometry for all edges
  const lineGeo = useMemo(() => {
    const positions: number[] = [];
    const colors:    number[] = [];

    for (const seg of segments) {
      const a = nodes.get(seg.startNodeId);
      const b = nodes.get(seg.endNodeId);
      if (!a || !b) continue;

      positions.push(a.position.x, a.position.y, a.position.z);
      positions.push(b.position.x, b.position.y, b.position.z);

      const isSelected = seg.id === selectedSegmentId;
      const c = new THREE.Color(isSelected ? "#ffffff" : NODE_COLORS[b.type] ?? "#888");
      colors.push(c.r, c.g, c.b, c.r, c.g, c.b);
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute("color",    new THREE.Float32BufferAttribute(colors, 3));
    return geo;
  }, [nodes, segments, selectedSegmentId]);

  return (
    <lineSegments geometry={lineGeo} renderOrder={5}>
      <lineBasicMaterial vertexColors linewidth={2} depthTest={false} />
    </lineSegments>
  );
}

// ── Individual node sphere ────────────────────────────────────────────────────

function NodeSphere({
  node,
  isSelected,
  onClick,
}: {
  node: { id: number; position: THREE.Vector3; type: string; radius: number };
  isSelected: boolean;
  onClick: () => void;
}) {
  const color  = NODE_COLORS[node.type] ?? "#888";
  const r      = NODE_RADII[node.type]  ?? 0.5;

  return (
    <mesh
      position={node.position.toArray() as [number, number, number]}
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      renderOrder={6}
    >
      <sphereGeometry args={[r, 8, 6]} />
      <meshStandardMaterial
        color={isSelected ? "#ffffff" : color}
        emissive={isSelected ? color : "#000"}
        emissiveIntensity={isSelected ? 0.8 : 0}
        roughness={0.4}
        depthTest={false}
        transparent
        opacity={0.9}
      />
    </mesh>
  );
}

// ── Contact ring indicator ────────────────────────────────────────────────────

function ContactRing({ position }: { position: THREE.Vector3 }) {
  const geo = useMemo(() => new THREE.TorusGeometry(1.2, 0.2, 6, 16), []);
  return (
    <mesh
      geometry={geo}
      position={position.toArray() as [number, number, number]}
      renderOrder={7}
    >
      <meshStandardMaterial color="#ef4444" emissive="#ff2200" emissiveIntensity={0.6} depthTest={false} />
    </mesh>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface DebugGraphOverlayProps {
  result:             TreeSupportResult;
  selectedSegmentId:  number | null;
  selectedNodeId:     number | null;
  onSegmentClick:     (id: number | null) => void;
  onNodeClick:        (id: number | null) => void;
}

export function DebugGraphOverlay({
  result,
  selectedSegmentId,
  selectedNodeId,
  onSegmentClick,
  onNodeClick,
}: DebugGraphOverlayProps) {
  const { nodes, segments } = result;

  const contactNodes = useMemo(
    () => [...nodes.values()].filter(n => n.type === "contact"),
    [nodes],
  );

  return (
    <group name="debug-graph-overlay">
      {/* Wire lines for all segments */}
      <SegmentLines
        result={result}
        selectedSegmentId={selectedSegmentId}
        onSegmentClick={onSegmentClick}
      />

      {/* Node spheres */}
      {[...nodes.values()].map(node => (
        <NodeSphere
          key={node.id}
          node={node}
          isSelected={node.id === selectedNodeId}
          onClick={() => onNodeClick(selectedNodeId === node.id ? null : node.id)}
        />
      ))}

      {/* Contact rings */}
      {contactNodes.map(node => (
        <ContactRing key={`ring-${node.id}`} position={node.position} />
      ))}
    </group>
  );
}

// ── Legend data (for sidebar) ─────────────────────────────────────────────────

export const DEBUG_LEGEND = [
  { type: "root",     color: "#60a5fa", label: "Root (build plate)" },
  { type: "trunk",    color: "#34d399", label: "Trunk node" },
  { type: "branch",   color: "#fbbf24", label: "Branch node" },
  { type: "tip",      color: "#f97316", label: "Tip node" },
  { type: "contact",  color: "#ef4444", label: "Contact point" },
  { type: "waypoint", color: "#94a3b8", label: "Waypoint (collision avoid)" },
] as const;
